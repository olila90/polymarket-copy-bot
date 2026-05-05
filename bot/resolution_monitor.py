"""
Détecte les marchés résolus en cherchant les événements REDEEM
sur les condition_ids de nos positions.

Chaque position stocke son propre `copied_from` (adresse du trader d'origine),
ce qui permet de détecter les résolutions même si le trader courant a changé.

Logique :
  REDEEM avec usdcSize > 0  → marché gagné (payout = shares × $1.00)
  REDEEM avec usdcSize = 0  → marché perdu (payout = $0)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config import DATA_API_BASE


def check_resolutions(positions: dict, since_ts: int) -> list[dict]:
    """
    Retourne la liste des positions résolues depuis since_ts.
    positions : dict {token_id: pos} du portfolio virtuel.
    Chaque pos doit contenir 'copied_from' (adresse du trader d'origine).

    Chaque élément retourné :
      {token_id, condition_id, market_title, won: bool}
    """
    if not positions:
        return []

    resolved = []

    for token_id, pos in positions.items():
        condition_id = pos.get("condition_id", "")
        trader_address = pos.get("copied_from", "")
        if not condition_id or not trader_address:
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
                usdc = float(ev.get("usdcSize", 0))
                resolved.append({
                    "token_id": token_id,
                    "condition_id": condition_id,
                    "market_title": pos.get("market_title", ""),
                    "outcome": pos.get("outcome", ""),
                    "won": usdc > 0,
                    "trader_payout_usdc": usdc,
                })
                break

        except Exception:
            continue

    return resolved
