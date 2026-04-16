"""
Boucle principale du Copy Trading Bot (paper trading).

Toutes les POLLING_INTERVAL_SEC secondes :
  - Si >LEADERBOARD_REFRESH_SEC depuis le dernier refresh : met à jour le top trader
  - Récupère les nouveaux trades du trader courant
  - Pour chaque nouveau trade BUY : exécute un paper trade proportionnel

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
from bot.activity_monitor import get_new_trades
from bot.resolution_monitor import check_resolutions
from api.clob_api import get_midpoint
from api.data_api import get_user_activity
import virtual.portfolio as portfolio_mod
from config import (
    INITIAL_BALANCE, MAX_POSITION_SIZE_PCT,
    POLLING_INTERVAL_SEC, LEADERBOARD_REFRESH_SEC, MAX_LOGS,
    DAILY_BUDGET_PCT, MIN_TRADE_SIZE_PCT, MAX_TRADE_SIZE_PCT, TRADE_FREQ_WINDOW_H,
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
        "logs": [],
    }


def estimate_daily_trades(address: str) -> int:
    """
    Estime le nombre de trades BUY que le trader fait par jour
    en regardant les dernières TRADE_FREQ_WINDOW_H heures.
    """
    since = int(time.time()) - TRADE_FREQ_WINDOW_H * 3600
    try:
        trades = get_user_activity(address, since_ts=since, limit=500, side="BUY")
        return max(len(trades), 1)
    except Exception:
        return 10  # valeur par défaut si API fail


def compute_trade_size_pct(n_trades: int) -> float:
    """
    Taille par trade = budget_journalier / nb_trades_estimé
    Clampée entre MIN et MAX.
    """
    raw = DAILY_BUDGET_PCT / n_trades
    return max(MIN_TRADE_SIZE_PCT, min(MAX_TRADE_SIZE_PCT, raw))


def load_state() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if BOT_STATE_FILE.exists():
        with open(BOT_STATE_FILE) as f:
            return json.load(f)
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
    """Met à jour le top trader depuis le leaderboard."""
    log(state, "Refresh leaderboard...")
    trader = get_top_trader()
    if not trader:
        log(state, "Impossible de récupérer le leaderboard.")
        return

    if trader["address"] != state.get("current_trader"):
        log(state, f"Nouveau trader sélectionné : {trader['username']} (PnL: ${trader['pnl']:,.0f})")
        # Démarrer depuis 2h en arrière max — évite de rattraper un historique trop ancien
        state["last_activity_check"] = int(time.time()) - 2 * 3600
        # Réinitialiser le sizing au changement de trader
        state["estimated_daily_trades"] = None
        state["dynamic_trade_size_pct"] = None

    state["current_trader"] = trader["address"]
    state["trader_username"] = trader["username"]
    state["trader_pnl"] = trader["pnl"]
    state["last_leaderboard_refresh"] = int(time.time())

    # Calculer le sizing dynamique dès le refresh
    n = estimate_daily_trades(trader["address"])
    pct = compute_trade_size_pct(n)
    state["estimated_daily_trades"] = n
    state["dynamic_trade_size_pct"] = round(pct, 4)
    log(state, f"Sizing dynamique : {n} trades/jour → {pct*100:.1f}% du portfolio par trade")


def process_trades(state: dict) -> None:
    """Récupère et copie les nouveaux trades du trader courant."""
    address = state.get("current_trader")
    if not address:
        return

    since_ts = state.get("last_activity_check", 0)
    new_trades = get_new_trades(address, since_ts=since_ts)

    if not new_trades:
        state["last_activity_check"] = int(time.time())
        return

    pf = portfolio_mod.load(INITIAL_BALANCE)

    for trade in new_trades:
        token_id = trade["token_id"]
        market_title = trade["market_title"] or f"Marché {trade['condition_id'][:8]}"

        # Récupérer le prix actuel (on achète au prix du marché, pas du trader original)
        current_price = get_midpoint(token_id)
        if current_price is None:
            # Fallback sur le prix du trade original
            current_price = trade["price"]
        if current_price <= 0 or current_price >= 1:
            log(state, f"Prix invalide ({current_price}) pour {market_title} — ignoré")
            continue

        # Sizing dynamique : budget_journalier / nb_trades_estimé
        trade_size_pct = state.get("dynamic_trade_size_pct") or compute_trade_size_pct(
            state.get("estimated_daily_trades") or 10
        )
        total_value = portfolio_mod.get_total_value(pf, {})
        amount = total_value * trade_size_pct

        # Vérifier la limite par marché
        pos = pf["positions"].get(token_id)
        if pos:
            existing_exposure = pos["cost_basis"]
            if (existing_exposure + amount) / total_value > MAX_POSITION_SIZE_PCT:
                log(state, f"Limite position atteinte pour {market_title} — ignoré")
                continue

        executed = portfolio_mod.paper_buy(
            pf,
            token_id=token_id,
            market_title=market_title,
            outcome=trade["outcome"],
            price=current_price,
            amount_usdc=amount,
            copied_from=address,
            condition_id=trade["condition_id"],
        )

        if executed:
            portfolio_mod.save(pf)
            state["total_trades_copied"] += 1
            log(state, (
                f"Trade copié : [{trade['outcome']}] {market_title[:50]} "
                f"@ {current_price:.3f} — ${amount:.1f} USDC"
            ))

    state["last_activity_check"] = int(time.time())


def process_resolutions(state: dict) -> None:
    """Détecte et clôture les positions résolues."""
    address = state.get("current_trader")
    if not address:
        return

    pf = portfolio_mod.load(INITIAL_BALANCE)
    if not pf["positions"]:
        return

    # Chercher les REDEEMs depuis au moins 48h en arrière
    # (un marché peut se résoudre avant l'ouverture de notre position si on a rattrapé l'historique)
    since_ts = int(time.time()) - 48 * 3600

    resolved = check_resolutions(address, pf["positions"], since_ts=since_ts)

    for res in resolved:
        token_id = res["token_id"]
        if token_id not in pf["positions"]:
            continue  # déjà clôturé

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
    print("  Polymarket Copy Bot — Paper Trading")
    print("=" * 60)

    state = load_state()

    # Forcer un refresh immédiat au démarrage
    if not state.get("current_trader"):
        refresh_trader(state)
        save_state(state)

    while True:
        try:
            now = int(time.time())

            # Refresh leaderboard si nécessaire
            if now - state.get("last_leaderboard_refresh", 0) >= LEADERBOARD_REFRESH_SEC:
                refresh_trader(state)

            # Vérifier l'activité du trader
            if state.get("current_trader"):
                process_resolutions(state)
                process_trades(state)
            else:
                log(state, "Aucun trader sélectionné, nouvelle tentative dans 60s...")

            save_state(state)

        except Exception as e:
            print(f"[CopyBot] Erreur inattendue: {e}")

        time.sleep(POLLING_INTERVAL_SEC)


if __name__ == "__main__":
    run()
