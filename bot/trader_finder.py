"""
Identifie le meilleur trader du leaderboard Polymarket.
Filtre les traders dont >MAX_SPORTS_RATIO de trades sont des paris sportifs
courts-termes (non copiables sans edge propriétaire).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from api.data_api import get_leaderboard, get_user_activity
from config import (
    LEADERBOARD_PERIOD, LEADERBOARD_METRIC, MAX_SPORTS_RATIO,
    SPORTS_KEYWORDS, TOP_N_TRADERS,
)


def _is_sports_title(title: str) -> bool:
    return any(kw in title for kw in SPORTS_KEYWORDS)


def _trader_sports_ratio(address: str, days: int = 7) -> float:
    """Ratio de trades sportifs courts-termes sur les N derniers jours."""
    since_ts = int(time.time()) - days * 86400
    try:
        trades = get_user_activity(address, since_ts=since_ts, limit=500, side="BUY")
        if not trades:
            return 0.0
        sports = sum(1 for t in trades if _is_sports_title(t.get("title", "")))
        return sports / len(trades)
    except Exception:
        return 0.0


def get_top_traders(n: int = TOP_N_TRADERS) -> list[dict]:
    """
    Retourne jusqu'à n traders qualifiés du leaderboard (dans l'ordre du classement).
    Qualifié = ratio sports < MAX_SPORTS_RATIO.
    Retourne une liste vide en cas d'erreur ou si aucun trader ne passe le filtre.
    """
    try:
        leaders = get_leaderboard(
            time_period=LEADERBOARD_PERIOD,
            order_by=LEADERBOARD_METRIC,
            limit=10,
        )
        if not leaders:
            return []

        qualified = []
        for top in leaders:
            if len(qualified) >= n:
                break
            address = top.get("proxyWallet", "")
            if not address:
                continue
            ratio = _trader_sports_ratio(address)
            if ratio >= MAX_SPORTS_RATIO:
                print(f"[TraderFinder] {top.get('userName', address)[:20]} rejeté — ratio sports {ratio:.0%}")
                continue
            qualified.append({
                "address": address,
                "username": top.get("userName", "Anonyme"),
                "pnl": float(top.get("pnl", 0)),
                "volume": float(top.get("vol", 0)),
                "rank": int(top.get("rank", 1)),
                "x_username": top.get("xUsername", ""),
                "sports_ratio": round(ratio, 2),
            })

        return qualified

    except Exception as e:
        print(f"[TraderFinder] Erreur leaderboard: {e}")
        return []


def get_top_trader() -> dict | None:
    """Compat : premier trader qualifié (utilisé par le dashboard)."""
    traders = get_top_traders(1)
    return traders[0] if traders else None


def get_leaderboard_top10() -> list[dict]:
    """Retourne le top 10 pour affichage dans le dashboard."""
    try:
        leaders = get_leaderboard(
            time_period=LEADERBOARD_PERIOD,
            order_by=LEADERBOARD_METRIC,
            limit=10,
        )
        result = []
        for entry in leaders:
            result.append({
                "rank": int(entry.get("rank", 0)),
                "address": entry.get("proxyWallet", ""),
                "username": entry.get("userName", "Anonyme"),
                "pnl": float(entry.get("pnl", 0)),
                "volume": float(entry.get("vol", 0)),
                "x_username": entry.get("xUsername", ""),
            })
        return result
    except Exception as e:
        print(f"[TraderFinder] Erreur top10: {e}")
        return []
