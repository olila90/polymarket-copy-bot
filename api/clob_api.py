"""
Client pour la Polymarket CLOB API et Gamma API (publiques).
Usage : récupérer les prix et les métadonnées des marchés.

Stratégie de prix :
  1. Gamma API : lastTradePrice (fiable, toujours présent pour marchés actifs)
  2. CLOB book : last_trade_price (fallback)
  3. CLOB book : mid des bids/asks (dernier recours)
"""
import json
import requests
from config import CLOB_API_BASE, GAMMA_API_BASE


def _get(base: str, path: str, params: dict = None) -> dict | list:
    url = f"{base}{path}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_market_by_token(token_id: str) -> dict | None:
    """
    Métadonnées du marché associé à un token_id via la Gamma API.
    Contient : question, lastTradePrice, bestBid, bestAsk, outcomePrices, tokens, etc.
    """
    try:
        data = _get(GAMMA_API_BASE, "/markets", {"clob_token_ids": token_id})
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception:
        return None


def get_midpoint(token_id: str) -> float | None:
    """
    Prix actuel d'un token (0.0 à 1.0).
    Priorité : Gamma lastTradePrice > CLOB book last_trade_price > mid bids/asks.
    Retourne None si le marché est introuvable ou résolu.
    """
    # 1. Gamma API — lastTradePrice + position du token dans outcomePrices
    try:
        market = get_market_by_token(token_id)
        if market:
            # Trouver l'index du token dans clobTokenIds pour mapper outcomePrices
            clob_token_ids = market.get("clobTokenIds") or []
            if isinstance(clob_token_ids, str):
                clob_token_ids = json.loads(clob_token_ids)

            outcome_prices_raw = market.get("outcomePrices")
            if outcome_prices_raw:
                outcome_prices = json.loads(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
                if token_id in clob_token_ids:
                    idx = clob_token_ids.index(token_id)
                    if idx < len(outcome_prices):
                        p = float(outcome_prices[idx])
                        if 0 < p < 1:
                            return p

            # Fallback : lastTradePrice du marché (si binaire et un seul token)
            ltp = market.get("lastTradePrice")
            if ltp is not None:
                p = float(ltp)
                if 0 < p < 1:
                    return p
    except Exception:
        pass

    # 2. CLOB book — last_trade_price
    try:
        book = _get(CLOB_API_BASE, "/book", {"token_id": token_id})
        ltp = book.get("last_trade_price")
        if ltp is not None:
            p = float(ltp)
            if 0 < p < 1:
                return p

        # 3. Mid bids/asks si spread raisonnable
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if bids and asks:
            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            spread = best_ask - best_bid
            if spread < 0.10:  # Spread < 10 cents = marché liquide
                mid = (best_bid + best_ask) / 2
                if 0 < mid < 1:
                    return mid
    except Exception:
        pass

    return None


def get_midpoints_batch(token_ids: list[str]) -> dict[str, float]:
    """
    Prix pour une liste de tokens. Retourne {token_id: price}.
    """
    prices = {}
    for token_id in token_ids:
        price = get_midpoint(token_id)
        if price is not None:
            prices[token_id] = price
    return prices
