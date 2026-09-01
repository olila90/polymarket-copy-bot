"""
Boucle principale du Copy Trading Bot (paper trading).

Toutes les POLLING_INTERVAL_SEC secondes :
  - Si >LEADERBOARD_REFRESH_SEC depuis le dernier refresh : met à jour les top traders
  - Récupère les nouveaux trades des TOP_N_TRADERS traders suivis
  - Pour chaque nouveau trade BUY qualifié : exécute un paper trade proportionnel
    (budget journalier réparti entre les traders)

Lancer : python bot/copy_bot.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from pathlib import Path
from datetime import datetime

from bot.trader_finder import get_top_traders
from bot.activity_monitor import get_new_trades, get_new_sells
from bot.resolution_monitor import check_resolutions
from api.clob_api import get_midpoint
from api.data_api import get_user_activity
import virtual.portfolio as portfolio_mod
from config import (
    INITIAL_BALANCE, MAX_POSITION_SIZE_PCT,
    POLLING_INTERVAL_SEC, LEADERBOARD_REFRESH_SEC, MAX_LOGS,
    DAILY_BUDGET_PCT, MIN_TRADE_SIZE_PCT, MAX_TRADE_SIZE_PCT, TRADE_FREQ_WINDOW_H,
    STOP_LOSS_PCT, MAX_SEEN_TX_HASHES,
    MAX_OPEN_POSITIONS, CONDITION_COOLDOWN_H, TOP_N_TRADERS,
    MAX_HOLD_DAYS, MAX_POSITIONS_PER_TRADER,
)

DATA_DIR = Path(__file__).parent.parent / "data"
BOT_STATE_FILE = DATA_DIR / "bot_state.json"


# ── État du bot ──────────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {
        # Liste des traders suivis :
        # [{address, username, pnl, sports_ratio, estimated_daily_trades, trade_size_pct}]
        "traders": [],
        "last_leaderboard_refresh": 0,
        "last_activity_check": int(time.time()),
        "total_trades_copied": 0,
        "seen_tx_hashes": [],
        "last_buy_per_condition": {},  # {condition_id: timestamp} — cooldown anti-DCA
        "stop_loss_triggered": False,
        "logs": [],
    }


def estimate_daily_trades(address: str) -> int:
    since = int(time.time()) - TRADE_FREQ_WINDOW_H * 3600
    try:
        trades = get_user_activity(address, since_ts=since, limit=500, side="BUY")
        return max(len(trades), 1)
    except Exception:
        return 10


def compute_trade_size_pct(n_trades: int, n_traders: int = 1) -> float:
    """Budget journalier réparti entre les traders suivis, divisé par la
    fréquence de trade estimée du trader, borné par les planchers/plafonds."""
    budget = DAILY_BUDGET_PCT / max(n_traders, 1)
    raw = budget / max(n_trades, 1)
    return max(MIN_TRADE_SIZE_PCT, min(MAX_TRADE_SIZE_PCT, raw))


def load_state() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if BOT_STATE_FILE.exists():
        with open(BOT_STATE_FILE) as f:
            state = json.load(f)
        # Migration : ajouter les clés manquantes des nouvelles versions
        state.setdefault("last_buy_per_condition", {})
        state.setdefault("stop_loss_triggered", False)
        if "traders" not in state:
            # Ancien format mono-trader → liste
            state["traders"] = []
            if state.get("current_trader"):
                state["traders"].append({
                    "address": state["current_trader"],
                    "username": state.get("trader_username") or "Anonyme",
                    "pnl": state.get("trader_pnl", 0.0),
                    "sports_ratio": None,
                    "estimated_daily_trades": state.get("estimated_daily_trades"),
                    "trade_size_pct": state.get("dynamic_trade_size_pct"),
                })
        return state
    return _default_state()


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    tmp = str(BOT_STATE_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, BOT_STATE_FILE)


def log(state: dict, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{ts} — {msg}"
    print(entry)
    state["logs"].append(entry)
    if len(state["logs"]) > MAX_LOGS:
        state["logs"] = state["logs"][-MAX_LOGS:]


# ── Logique principale ────────────────────────────────────────────────────────

def refresh_traders(state: dict) -> None:
    log(state, "Refresh leaderboard...")
    top = get_top_traders(TOP_N_TRADERS)
    if not top:
        log(state, "Impossible de récupérer le leaderboard.")
        return

    previous = {t["address"] for t in state.get("traders", [])}
    n_traders = len(top)

    traders = []
    for trader in top:
        if trader["address"] not in previous:
            sports_info = f", ratio sports {trader.get('sports_ratio', 0):.0%}"
            log(state, f"Nouveau trader suivi : {trader['username']} (PnL: ${trader['pnl']:,.0f}{sports_info})")

        n = estimate_daily_trades(trader["address"])
        pct = compute_trade_size_pct(n, n_traders)
        traders.append({
            "address": trader["address"],
            "username": trader["username"],
            "pnl": trader["pnl"],
            "sports_ratio": trader.get("sports_ratio"),
            "estimated_daily_trades": n,
            "trade_size_pct": round(pct, 4),
        })
        log(state, f"Sizing {trader['username'][:20]} : {n} trades/jour → {pct*100:.1f}% du portfolio par trade")

    dropped = previous - {t["address"] for t in traders}
    if dropped:
        names = [t["username"] for t in state.get("traders", []) if t["address"] in dropped]
        log(state, f"Traders retirés du suivi : {', '.join(names)}")

    state["traders"] = traders
    # Registre address → username persistant (attribution P&L même après rotation)
    names = state.setdefault("trader_names", {})
    for t in traders:
        names[t["address"]] = t["username"]
    state["last_leaderboard_refresh"] = int(time.time())


def get_live_prices(positions: dict) -> dict:
    """Récupère le prix midpoint actuel pour chaque position ouverte."""
    prices = {}
    for token_id in positions:
        p = get_midpoint(token_id)
        if p is not None:
            prices[token_id] = p
    return prices


def process_sells(state: dict) -> None:
    """Copie les SELL des traders suivis : ferme nos positions correspondantes au prix marché."""
    traders = state.get("traders", [])
    if not traders:
        return

    pf = portfolio_mod.load(INITIAL_BALANCE)
    if not pf["positions"]:
        return

    since_ts = state.get("last_activity_check", 0)
    seen_tx_hashes = set(state.get("seen_tx_hashes", []))

    sell_trades = []
    for trader in traders:
        for trade in get_new_sells(trader["address"], since_ts=since_ts, seen_tx_hashes=seen_tx_hashes):
            trade["seller_address"] = trader["address"]
            sell_trades.append(trade)

    for trade in sell_trades:
        token_id = trade["token_id"]
        pos = pf["positions"].get(token_id)
        if pos is None:
            continue
        # Ne fermer que si c'est le trader d'origine de la position qui vend
        if pos.get("copied_from") and pos["copied_from"] != trade["seller_address"]:
            continue

        current_price = get_midpoint(token_id)
        if current_price is None:
            current_price = trade["price"]

        result = portfolio_mod.paper_sell(pf, token_id, current_price)
        if result:
            portfolio_mod.save(pf)
            tx_hash = trade.get("tx_hash", "")
            if tx_hash:
                seen_tx_hashes.add(tx_hash)
            sign = "+" if result["pnl"] >= 0 else ""
            log(state, (
                f"SELL copié : [{result['outcome']}] {result['market_title'][:45]} "
                f"@ {current_price:.3f} → P&L {sign}{result['pnl']:.2f}"
            ))

    state["seen_tx_hashes"] = list(seen_tx_hashes)[-MAX_SEEN_TX_HASHES:]


def process_trades(state: dict) -> None:
    traders = state.get("traders", [])
    if not traders:
        return

    pf = portfolio_mod.load(INITIAL_BALANCE)

    # Stop-loss avec prix de marché réels (évite la sous-estimation du risque)
    live_prices = get_live_prices(pf["positions"])
    total_value = portfolio_mod.get_total_value(pf, live_prices)
    stop_loss_floor = pf["initial_balance"] * (1 - STOP_LOSS_PCT)
    if total_value < stop_loss_floor:
        if not state.get("stop_loss_triggered"):
            log(state, f"STOP-LOSS déclenché — portfolio ${total_value:.2f} < seuil ${stop_loss_floor:.2f}. Trades suspendus.")
            state["stop_loss_triggered"] = True
        state["last_activity_check"] = int(time.time())
        return
    else:
        state["stop_loss_triggered"] = False

    seen_tx_hashes = set(state.get("seen_tx_hashes", []))
    since_ts = state.get("last_activity_check", 0)

    # Collecter les nouveaux BUY de chaque trader suivi (annotés de leur origine)
    new_trades = []
    for trader in traders:
        for trade in get_new_trades(trader["address"], since_ts=since_ts, seen_tx_hashes=seen_tx_hashes):
            trade["trader"] = trader
            new_trades.append(trade)
    new_trades.sort(key=lambda t: t["ts"])

    if not new_trades:
        state["last_activity_check"] = int(time.time())
        return

    now = int(time.time())
    last_buy_per_condition = state.get("last_buy_per_condition", {})
    cooldown_sec = int(CONDITION_COOLDOWN_H * 3600)

    # Précalculer l'exposition par condition_id (somme des cost_basis des positions ouvertes)
    # et le nombre de positions ouvertes par trader copié
    condition_exposure = {}
    positions_per_trader = {}
    for tid, pos in pf["positions"].items():
        cid = pos.get("condition_id", "")
        condition_exposure[cid] = condition_exposure.get(cid, 0) + pos["cost_basis"]
        src = pos.get("copied_from", "")
        positions_per_trader[src] = positions_per_trader.get(src, 0) + 1

    for trade in new_trades:
        token_id = trade["token_id"]
        condition_id = trade["condition_id"]
        market_title = trade["market_title"] or f"Marché {condition_id[:8]}"

        # Cooldown par condition_id (anti-DCA : on ne copie que la première entrée)
        last_buy_ts = last_buy_per_condition.get(condition_id, 0)
        if now - last_buy_ts < cooldown_sec:
            continue

        # Limite du nombre de positions ouvertes
        if len(pf["positions"]) >= MAX_OPEN_POSITIONS:
            log(state, f"Max positions atteint ({MAX_OPEN_POSITIONS}) — ignoré")
            continue

        # Cap par trader : un seul trader ne peut pas remplir le book
        trader_addr = trade["trader"]["address"]
        if positions_per_trader.get(trader_addr, 0) >= MAX_POSITIONS_PER_TRADER:
            log(state, f"Cap {MAX_POSITIONS_PER_TRADER} positions/trader atteint pour {trade['trader']['username'][:20]} — ignoré")
            continue

        # Prix actuel
        current_price = get_midpoint(token_id)
        if current_price is None:
            current_price = trade["price"]
        if current_price <= 0 or current_price >= 1:
            log(state, f"Prix invalide ({current_price}) pour {market_title} — ignoré")
            continue

        # Sizing dynamique propre au trader d'origine
        trader = trade["trader"]
        trade_size_pct = trader.get("trade_size_pct") or compute_trade_size_pct(
            trader.get("estimated_daily_trades") or 10, len(traders)
        )
        # Recalculer total_value avec le portfolio à jour (après achats précédents du batch)
        current_total = portfolio_mod.get_total_value(pf, {})
        amount = current_total * trade_size_pct

        # Limite d'exposition par condition_id (couvre corrélation intra-match)
        existing_cond_exposure = condition_exposure.get(condition_id, 0)
        if (existing_cond_exposure + amount) / current_total > MAX_POSITION_SIZE_PCT:
            log(state, f"Limite condition atteinte pour {market_title[:40]} — ignoré")
            continue

        executed = portfolio_mod.paper_buy(
            pf,
            token_id=token_id,
            market_title=market_title,
            outcome=trade["outcome"],
            price=current_price,
            amount_usdc=amount,
            copied_from=trader["address"],
            condition_id=condition_id,
            trader_price=trade["price"],
        )

        if executed:
            portfolio_mod.save(pf)
            state["total_trades_copied"] += 1
            tx_hash = trade.get("tx_hash", "")
            if tx_hash:
                seen_tx_hashes.add(tx_hash)
            # Mettre à jour le cooldown, l'exposition et le compteur par trader
            last_buy_per_condition[condition_id] = now
            condition_exposure[condition_id] = existing_cond_exposure + amount
            positions_per_trader[trader_addr] = positions_per_trader.get(trader_addr, 0) + 1
            log(state, (
                f"Trade copié ({trader['username'][:20]}) : [{trade['outcome']}] {market_title[:50]} "
                f"@ {current_price:.3f} — ${amount:.1f} USDC"
            ))

    state["last_buy_per_condition"] = last_buy_per_condition
    all_hashes = list(seen_tx_hashes)
    state["seen_tx_hashes"] = all_hashes[-MAX_SEEN_TX_HASHES:]
    state["last_activity_check"] = int(time.time())


def process_stale_positions(state: dict) -> None:
    """Sortie forcée des positions plus vieilles que MAX_HOLD_DAYS.
    Filet de sécurité anti-gel : une position qui ne se résout pas (marché
    archivé, trader parti) ne doit pas occuper un slot indéfiniment."""
    pf = portfolio_mod.load(INITIAL_BALANCE)
    if not pf["positions"]:
        return

    now = int(time.time())
    max_age_sec = MAX_HOLD_DAYS * 86400

    for token_id in list(pf["positions"]):
        pos = pf["positions"][token_id]
        if now - pos.get("opened_at", now) < max_age_sec:
            continue

        price = get_midpoint(token_id)
        if price is None:
            # Aucune donnée de marché : sortie neutre au prix d'entrée (P&L 0)
            price = pos["avg_price"]
            log(state, f"Position expirée sans prix marché : {pos['market_title'][:40]} — sortie neutre")

        result = portfolio_mod.paper_sell(pf, token_id, price)
        if result:
            portfolio_mod.save(pf)
            sign = "+" if result["pnl"] >= 0 else ""
            log(state, (
                f"EXPIRÉ (>{MAX_HOLD_DAYS}j) : [{result['outcome']}] {result['market_title'][:45]} "
                f"@ {price:.3f} → P&L {sign}{result['pnl']:.2f}"
            ))


def process_resolutions(state: dict) -> None:
    pf = portfolio_mod.load(INITIAL_BALANCE)
    if not pf["positions"]:
        return

    # Chercher les REDEEMs depuis 48h en arrière
    # resolution_monitor utilise le copied_from de chaque position
    since_ts = int(time.time()) - 48 * 3600
    resolved = check_resolutions(pf["positions"], since_ts=since_ts)

    for res in resolved:
        token_id = res["token_id"]
        if token_id not in pf["positions"]:
            continue

        result = portfolio_mod.paper_close(pf, token_id, won=res["won"])
        if result:
            portfolio_mod.save(pf)
            emoji = "WIN" if res["won"] else "LOSS"
            log(state, (
                f"[{emoji}] {result['market_title'][:45]} [{result['outcome']}] "
                f"→ payout ${result['payout']:.2f} | P&L ${result['pnl']:+.2f}"
            ))


# ── Boucle principale ─────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("  Polymarket Copy Bot — Paper Trading v2")
    print("=" * 60)

    state = load_state()

    if not state.get("traders"):
        refresh_traders(state)
        save_state(state)

    while True:
        try:
            now = int(time.time())

            if now - state.get("last_leaderboard_refresh", 0) >= LEADERBOARD_REFRESH_SEC:
                refresh_traders(state)

            if state.get("traders"):
                process_resolutions(state)
                process_stale_positions(state)
                process_sells(state)
                process_trades(state)
            else:
                log(state, "Aucun trader qualifié, nouvelle tentative dans 60s...")

            save_state(state)

        except Exception as e:
            print(f"[CopyBot] Erreur inattendue: {e}")

        time.sleep(POLLING_INTERVAL_SEC)


if __name__ == "__main__":
    run()
