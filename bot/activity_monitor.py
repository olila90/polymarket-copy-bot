"""
Surveille l'activité d'un trader et détecte les nouveaux trades à copier.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time as _time
from api.data_api import get_user_activity
from config import MIN_TRADE_USD, MAX_TRADE_AGE_H

# Mots-clés indiquant un marché sportif à exclure (edge non transférable)
_SPORTS_KEYWORDS = (
    "O/U", " vs. ", "Spread:", "Over/Under", "Total:", "Moneyline",
    "NBA", "NFL", "NHL", "MLB", "NCAA", "MLS", "WNBA",
    " Finals", "Super Bowl", "World Series", "Grand Prix",
)


def _is_sports_market(title: str) -> bool:
    return any(kw in title for kw in _SPORTS_KEYWORDS)


def get_new_trades(address: str, since_ts: int, seen_tx_hashes: set | None = None) -> list[dict]:
    """
    Récupère les nouveaux trades BUY du trader depuis since_ts.
    Filtre :
      - montant < MIN_TRADE_USD
      - trades > MAX_TRADE_AGE_H heures (edge périmé)
      - marchés sportifs O/U / Spread (50/50, non copiables)
      - tx_hash déjà traités (déduplication)
    Retourne les trades du plus ancien au plus récent.
    """
    if seen_tx_hashes is None:
        seen_tx_hashes = set()

    try:
        raw = get_user_activity(address, since_ts=since_ts, limit=100, side="BUY")
    except Exception as e:
        print(f"[ActivityMonitor] Erreur API activité: {e}")
        return []

    max_age_ts = int(_time.time()) - int(MAX_TRADE_AGE_H * 3600)

    trades = []
    for t in raw:
        ts = t.get("timestamp", 0)
        if ts <= since_ts:
            continue
        if ts < max_age_ts:
            continue
        usdcSize = float(t.get("usdcSize", 0))
        if usdcSize < MIN_TRADE_USD:
            continue

        title = t.get("title", "")
        if _is_sports_market(title):
            continue

        tx_hash = t.get("transactionHash", "")
        if tx_hash and tx_hash in seen_tx_hashes:
            continue

        trades.append({
            "ts": ts,
            "condition_id": t.get("conditionId", ""),
            "token_id": t.get("asset", ""),
            "outcome": t.get("outcome", ""),
            "market_title": title,
            "price": float(t.get("price", 0)),
            "shares": float(t.get("size", 0)),
            "usdc_size": usdcSize,
            "side": t.get("side", "BUY"),
            "tx_hash": tx_hash,
        })

    return sorted(trades, key=lambda x: x["ts"])


def get_new_sells(address: str, since_ts: int, seen_tx_hashes: set | None = None) -> list[dict]:
    """
    Récupère les nouveaux trades SELL du trader depuis since_ts.
    Utilisé pour copier les sorties : si le trader vend, on ferme notre position.
    """
    if seen_tx_hashes is None:
        seen_tx_hashes = set()

    try:
        raw = get_user_activity(address, since_ts=since_ts, limit=100, side="SELL")
    except Exception as e:
        print(f"[ActivityMonitor] Erreur API activité SELL: {e}")
        return []

    max_age_ts = int(_time.time()) - int(MAX_TRADE_AGE_H * 3600)

    trades = []
    for t in raw:
        ts = t.get("timestamp", 0)
        if ts <= since_ts:
            continue
        if ts < max_age_ts:
            continue
        tx_hash = t.get("transactionHash", "")
        if tx_hash and tx_hash in seen_tx_hashes:
            continue
        trades.append({
            "ts": ts,
            "condition_id": t.get("conditionId", ""),
            "token_id": t.get("asset", ""),
            "outcome": t.get("outcome", ""),
            "market_title": t.get("title", ""),
            "price": float(t.get("price", 0)),
            "shares": float(t.get("size", 0)),
            "usdc_size": float(t.get("usdcSize", 0)),
            "side": "SELL",
            "tx_hash": tx_hash,
        })

    return sorted(trades, key=lambda x: x["ts"])
