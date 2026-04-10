"""
Identifie le meilleur trader du leaderboard Polymarket.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.data_api import get_leaderboard
from config import LEADERBOARD_PERIOD, LEADERBOARD_METRIC


def get_top_trader() -> dict | None:
    """
    Retourne le trader #1 du leaderboard selon la période et métrique configurées.
    Retourne None en cas d'erreur.
    """
    try:
        leaders = get_leaderboard(
            time_period=LEADERBOARD_PERIOD,
            order_by=LEADERBOARD_METRIC,
            limit=10,
        )
        if not leaders:
            return None
        top = leaders[0]
        return {
            "address": top.get("proxyWallet", ""),
            "username": top.get("userName", "Anonyme"),
            "pnl": float(top.get("pnl", 0)),
            "volume": float(top.get("vol", 0)),
            "rank": int(top.get("rank", 1)),
            "x_username": top.get("xUsername", ""),
        }
    except Exception as e:
        print(f"[TraderFinder] Erreur leaderboard: {e}")
        return None


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
