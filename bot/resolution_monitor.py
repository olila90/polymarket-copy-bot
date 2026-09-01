"""
Détecte les marchés résolus en interrogeant la résolution RÉELLE du marché
(Gamma API) pour chaque position ouverte.

⚠️ L'ancienne approche (REDEEM du trader copié sur le condition_id) était
fausse : un market maker détient souvent LES DEUX côtés d'un marché, donc il
encaisse un REDEEM > 0 même quand NOTRE côté a perdu — toutes nos défaites
étaient comptées comme des victoires (bug du +57 000% du 28/07/2026).

Logique :
  1. Gamma : marché closed + prix final de NOTRE token ≥ 0.999 → gagné, ≤ 0.001 → perdu
  2. Fallback CLOB /markets/{condition_id} : Gamma archive les vieux marchés sportifs
     (réponse vide sur clob_token_ids) — le champ tokens[].winner de la CLOB reste
     disponible et fait foi (cause du gel du bot 28/07→01/09/2026).
  sinon (marché ouvert, prix intermédiaire, données absentes) → pas résolu
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from api.clob_api import get_market_by_token, get_clob_market


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


def _gamma_resolution(token_id: str) -> bool | None:
    """Résolution via Gamma. True/False si tranchée, None sinon."""
    market = get_market_by_token(token_id)
    if not market or not market.get("closed"):
        return None
    price = _final_token_price(market, token_id)
    if price is None:
        return None
    if price >= 0.999:
        return True
    if price <= 0.001:
        return False
    return None


def _clob_resolution(condition_id: str, token_id: str) -> bool | None:
    """Résolution via CLOB tokens[].winner. True/False si tranchée, None sinon."""
    if not condition_id:
        return None
    market = get_clob_market(condition_id)
    if not market or not market.get("closed"):
        return None
    tokens = market.get("tokens") or []
    # Marché fermé mais pas encore réglé : aucun winner désigné
    if not any(t.get("winner") for t in tokens):
        return None
    our = next((t for t in tokens if t.get("token_id") == token_id), None)
    if our is None:
        return None
    return bool(our.get("winner"))


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
            won = _gamma_resolution(token_id)
            if won is None:
                won = _clob_resolution(pos.get("condition_id", ""), token_id)
            if won is None:
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
