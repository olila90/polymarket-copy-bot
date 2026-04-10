"""
Détecte les marchés résolus en cherchant les événements REDEEM
du trader copié sur les condition_ids de nos positions.

Logique :
  REDEEM avec usdcSize > 0  → marché gagné (payout = shares × $1.00)
  REDEEM avec usdcSize = 0  → marché perdu (payout = $0)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import requests
from config import DATA_API_BASE


def check_resolutions(trader_address: str, positions: dict, since_ts: int) -> list[dict]:
    """
    Retourne la liste des positions résolues depuis since_ts.
    positions : dict {token_id: pos} du portfolio virtuel.

    Chaque élément retourné :
      {token_id, condition_id, market_title, won: bool}
    """
    if not positions:
        return []

    resolved = []

    for token_id, pos in positions.items():
        condition_id = pos.get("condition_id", "")
        if not condition_id:
            continue

        try:
            r = requests.get(
                f"{DATA_API_BASE}/activity",
                params={
                    "user": trader_address,
                    "market": condition_id,
                    "type": "REDEEM",
                    "start": since_ts,
                    "limit": 5,
                },
                timeout=15,
            )
            if r.status_code != 200:
                continue

            events = r.json()
            if not isinstance(events, list):
                continue

            for ev in events:
                if ev.get("type") != "REDEEM":
                    continue
                # usdcSize > 0 → position gagnante, 0 → perdante
                usdc = float(ev.get("usdcSize", 0))
                resolved.append({
                    "token_id": token_id,
                    "condition_id": condition_id,
                    "market_title": pos.get("market_title", ""),
                    "outcome": pos.get("outcome", ""),
                    "won": usdc > 0,
                    "trader_payout_usdc": usdc,
                })
                break  # un seul REDEEM par marché suffit

        except Exception:
            continue

    return resolved
