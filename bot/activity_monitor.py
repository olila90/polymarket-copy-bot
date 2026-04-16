"""
Surveille l'activité d'un trader et détecte les nouveaux trades à copier.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time as _time
from api.data_api import get_user_activity
from config import MIN_TRADE_USD, MAX_TRADE_AGE_H


def get_new_trades(address: str, since_ts: int) -> list[dict]:
    """
    Récupère les nouveaux trades BUY du trader depuis since_ts.
    Filtre :
      - montant < MIN_TRADE_USD
      - trades plus vieux que MAX_TRADE_AGE_H heures (évite les vieux historiques)
    Retourne les trades du plus ancien au plus récent.
    """
    try:
        raw = get_user_activity(address, since_ts=since_ts, limit=100, side="BUY")
    except Exception as e:
        print(f"[ActivityMonitor] Erreur API activité: {e}")
        return []

    max_age_ts = int(_time.time()) - MAX_TRADE_AGE_H * 3600

    trades = []
    for t in raw:
        ts = t.get("timestamp", 0)
        if ts <= since_ts:
            continue
        # Ignorer les trades trop anciens (vieux historique rattrapé)
        if ts < max_age_ts:
            continue
        usdcSize = float(t.get("usdcSize", 0))
        if usdcSize < MIN_TRADE_USD:
            continue

        # Construire un objet normalisé
        trades.append({
            "ts": ts,
            "condition_id": t.get("conditionId", ""),
            "token_id": t.get("asset", ""),      # Polymarket renvoie l'asset ID
            "outcome": t.get("outcome", ""),
            "market_title": t.get("title", ""),
            "price": float(t.get("price", 0)),
            "shares": float(t.get("size", 0)),
            "usdc_size": usdcSize,
            "side": t.get("side", "BUY"),
            "tx_hash": t.get("transactionHash", ""),
        })

    # Du plus ancien au plus récent pour les rejouer dans l'ordre
    return sorted(trades, key=lambda x: x["ts"])
