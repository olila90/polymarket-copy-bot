"""
Boucle principale du Copy Trading Bot (paper trading).

Toutes les POLLING_INTERVAL_SEC secondes :
  - Si >LEADERBOARD_REFRESH_SEC depuis le dernier refresh : met à jour le top trader
  - Récupère les nouveaux trades du trader courant
  - Pour chaque nouveau trade BUY qualifié : exécute un paper trade proportionnel

Lancer : python bot/copy_bot.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from pathlib import Path
from datetime import datetime

from bot.trader_finder import get_top_trader
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
    MAX_OPEN_POSITIONS, CONDITION_COOLDOWN_H,
)

DATA_DIR = Path(__file__).parent.parent / "data"
BOT_STATE_FILE = DATA_DIR / "bot_state.json"


# ── État du bot ──────────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {
        "current_trader": None,
        "trader_username": None,
        "trader_pnl": 0.0,
        "last_leaderboard_refresh": 0,
        "last_activity_check": int(time.time()),
        "total_trades_copied": 0,
        "estimated_daily_trades": None,
        "dynamic_trade_size_pct": None,
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


def compute_trade_size_pct(n_trades: int) -> float:
    raw = DAILY_BUDGET_PCT / n_trades
    return max(MIN_TRADE_SIZE_PCT, min(MAX_TRADE_SIZE_PCT, raw))


def load_state() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if BOT_STATE_FILE.exists():
        with open(BOT_STATE_FILE) as f:
            state = json.load(f)
        # Migration : ajouter les clés manquantes des nouvelles versions
        state.setdefault("last_buy_per_condition", {})
        state.setdefault("stop_loss_triggered", False)
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

def refresh_trader(state: dict) -> None:
    log(state, "Refresh leaderboard...")
    trader = get_top_trader()
    if not trader:
        log(state, "Impossible de récupérer le leaderboard.")
        return

    if trader["address"] != state.get("current_trader"):
        sports_info = f", ratio sports {trader.get('sports_ratio', 0):.0%}" if "sports_ratio" in trader else ""
        log(state, f"Nouveau trader sélectionné : {trader['username']} (PnL: ${trader['pnl']:,.0f}{sports_info})")
        state["last_activity_check"] = int(time.time()) - 2 * 3600
        state["estimated_daily_trades"] = None
        state["dynamic_trade_size_pct"] = None

    state["current_trader"] = trader["address"]
    state["trader_username"] = trader["username"]
    state["trader_pnl"] = trader["pnl"]
    state["last_leaderboard_refresh"] = int(time.time())

    n = estimate_daily_trades(trader["address"])
    pct = compute_trade_size_pct(n)
    state["estimated_daily_trades"] = n
    state["dynamic_trade_size_pct"] = round(pct, 4)
    log(state, f"Sizing dynamique : {n} trades/jour → {pct*100:.1f}% du portfolio par trade")


def get_live_prices(positions: dict) -> dict:
    """Récupère le prix midpoint actuel pour chaque position ouverte."""
    prices = {}
    for token_id in positions:
        p = get_midpoint(token_id)
        if p is not None:
            prices[token_id] = p
    return prices


def process_sells(state: dict) -> None:
    """Copie les SELL du trader : ferme nos positions correspondantes au prix marché."""
    address = state.get("current_trader")
    if not address:
        return

    pf = portfolio_mod.load(INITIAL_BALANCE)
    if not pf["positions"]:
        return

    since_ts = state.get("last_activity_check", 0)
    seen_tx_hashes = set(state.get("seen_tx_hashes", []))
    sell_trades = get_new_sells(address, since_ts=since_ts, seen_tx_hashes=seen_tx_hashes)

    for trade in sell_trades:
        token_id = trade["token_id"]
        if token_id not in pf["positions"]:
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
    address = state.get("current_trader")
    if not address:
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
    new_trades = get_new_trades(address, since_ts=since_ts, seen_tx_hashes=seen_tx_hashes)

    if not new_trades:
        state["last_activity_check"] = int(time.time())
        return

    now = int(time.time())
    last_buy_per_condition = state.get("last_buy_per_condition", {})
    cooldown_sec = int(CONDITION_COOLDOWN_H * 3600)

    # Précalculer l'exposition par condition_id (somme des cost_basis des positions ouvertes)
    condition_exposure = {}
    for tid, pos in pf["positions"].items():
        cid = pos.get("condition_id", "")
        condition_exposure[cid] = condition_exposure.get(cid, 0) + pos["cost_basis"]

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

        # Prix actuel
        current_price = get_midpoint(token_id)
        if current_price is None:
            current_price = trade["price"]
        if current_price <= 0 or current_price >= 1:
            log(state, f"Prix invalide ({current_price}) pour {market_title} — ignoré")
            continue

        # Sizing dynamique
        trade_size_pct = state.get("dynamic_trade_size_pct") or compute_trade_size_pct(
            state.get("estimated_daily_trades") or 10
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
            copied_from=address,
            condition_id=condition_id,
        )

        if executed:
            portfolio_mod.save(pf)
            state["total_trades_copied"] += 1
            tx_hash = trade.get("tx_hash", "")
            if tx_hash:
                seen_tx_hashes.add(tx_hash)
            # Mettre à jour le cooldown et l'exposition en mémoire
            last_buy_per_condition[condition_id] = now
            condition_exposure[condition_id] = existing_cond_exposure + amount
            log(state, (
                f"Trade copié : [{trade['outcome']}] {market_title[:50]} "
                f"@ {current_price:.3f} — ${amount:.1f} USDC"
            ))

    state["last_buy_per_condition"] = last_buy_per_condition
    all_hashes = list(seen_tx_hashes)
    state["seen_tx_hashes"] = all_hashes[-MAX_SEEN_TX_HASHES:]
    state["last_activity_check"] = int(time.time())


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

    if not state.get("current_trader"):
        refresh_trader(state)
        save_state(state)

    while True:
        try:
            now = int(time.time())

            if now - state.get("last_leaderboard_refresh", 0) >= LEADERBOARD_REFRESH_SEC:
                refresh_trader(state)

            if state.get("current_trader"):
                process_resolutions(state)
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
