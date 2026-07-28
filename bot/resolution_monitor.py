"""
Détecte les marchés résolus en interrogeant la résolution RÉELLE du marché
(Gamma API) pour chaque position ouverte.

⚠️ L'ancienne approche (REDEEM du trader copié sur le condition_id) était
fausse : un market maker détient souvent LES DEUX côtés d'un marché, donc il
encaisse un REDEEM > 0 même quand NOTRE côté a perdu — toutes nos défaites
étaient comptées comme des victoires (bug du +57 000% du 28/07/2026).

Logique :
  marché closed + prix final de NOTRE token ≥ 0.999 → gagné
  marché closed + prix final de NOTRE token ≤ 0.001 → perdu
  sinon (marché ouvert, prix intermédiaire, données absentes) → pas résolu
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from api.clob_api import get_market_by_token


def _final_token_price(market: dict, token_id: str) -> float | None:
    """Prix final de token_id dans le marché Gamma, ou None si introuvable."""
    try:
        clob_token_ids = market.get("clobTokenIds") or []
        if isinstance(clob_token_ids, str):
            clob_token_ids = json.loads(clob_token_ids)

        outcome_prices = market.get("outcomePrices")
        if isinstance(outcome_prices, str):
            outcome_prices = json.loads(outcome_prices)
        if not outcome_prices or token_id not in clob_token_ids:
            return None

        idx = clob_token_ids.index(token_id)
        if idx >= len(outcome_prices):
            return None
        return float(outcome_prices[idx])
    except Exception:
        return None


def check_resolutions(positions: dict, since_ts: int = 0) -> list[dict]:
    """
    Retourne la liste des positions résolues.
    positions : dict {token_id: pos} du portfolio virtuel.
    since_ts : conservé pour compatibilité d'appel (non utilisé).

    Chaque élément retourné :
      {token_id, condition_id, market_title, outcome, won: bool}
    """
    if not positions:
        return []

    resolved = []

    for token_id, pos in positions.items():
        try:
            market = get_market_by_token(token_id)
            if not market:
                continue
            if not market.get("closed"):
                continue

            price = _final_token_price(market, token_id)
            if price is None:
                continue

            # Ne conclure que sur une résolution franche (1.0 ou 0.0).
            # Un marché fermé avec prix intermédiaire n'est pas encore réglé.
            if price >= 0.999:
                won = True
            elif price <= 0.001:
                won = False
            else:
                continue

            resolved.append({
                "token_id": token_id,
                "condition_id": pos.get("condition_id", ""),
                "market_title": pos.get("market_title", ""),
                "outcome": pos.get("outcome", ""),
                "won": won,
            })

        except Exception:
            continue

    return resolved
