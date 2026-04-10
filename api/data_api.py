"""
Client pour la Polymarket Data API (publique, pas d'auth).
Endpoints : leaderboard, activité trader, positions.
"""
import time
import requests
from config import DATA_API_BASE


def _get(path: str, params: dict = None) -> list | dict:
    url = f"{DATA_API_BASE}{path}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_leaderboard(time_period: str = "MONTH", order_by: str = "PNL", limit: int = 10) -> list[dict]:
    """
    Retourne les meilleurs traders.
    time_period : DAY, WEEK, MONTH, ALL
    order_by    : PNL, VOL
    """
    data = _get("/v1/leaderboard", {
        "timePeriod": time_period,
        "orderBy": order_by,
        "limit": limit,
    })
    return data if isinstance(data, list) else []


def get_user_activity(
    address: str,
    since_ts: int = None,
    limit: int = 100,
    trade_type: str = "TRADE",
    side: str = "BUY",
) -> list[dict]:
    """
    Retourne les trades récents d'un utilisateur.
    since_ts : timestamp Unix, ne retourne que les trades APRÈS cette date.
    """
    params = {
        "user": address,
        "limit": limit,
        "type": trade_type,
        "sortBy": "TIMESTAMP",
        "sortDirection": "DESC",
    }
    if side:
        params["side"] = side
    if since_ts:
        params["start"] = since_ts

    data = _get("/activity", params)
    return data if isinstance(data, list) else []


def get_user_positions(address: str) -> list[dict]:
    """Positions ouvertes d'un utilisateur."""
    data = _get("/positions", {"user": address})
    return data if isinstance(data, list) else []
