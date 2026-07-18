"""Test rapide : filtre line-bet, sizing multi-traders, sélection top 3 (API réelle)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from bot.trader_finder import get_top_traders
from bot.activity_monitor import _is_line_bet
from bot.copy_bot import compute_trade_size_pct

# Filtre : paris de ligne exclus, autres marchés sportifs autorisés
assert _is_line_bet("Lakers vs Celtics O/U 220.5") is True
assert _is_line_bet("Spread: Chiefs -3.5") is True
assert _is_line_bet("Over/Under 2.5 goals") is True
assert _is_line_bet("Exact Score: France 3 - 2 Morocco?") is False
assert _is_line_bet("Will Real Madrid win the Champions League?") is False
assert _is_line_bet("ITF Columbus: Abanda vs Grubor") is False
print("Filtre line-bet OK")

# Sizing : budget 15% réparti sur 3 traders -> 5% chacun, borné [2%, 5%]
assert abs(compute_trade_size_pct(1, 3) - 0.05) < 1e-9
assert abs(compute_trade_size_pct(100, 3) - 0.02) < 1e-9
assert abs(compute_trade_size_pct(1, 1) - 0.05) < 1e-9
assert abs(compute_trade_size_pct(3, 3) - 0.02) < 1e-9   # 5%/3 = 1.67% -> plancher 2%
print("Sizing OK")

# Sélection top 3 avec leaderboard simulé (l'API réelle est testée en prod)
import bot.trader_finder as tf
import bot.copy_bot as cb

fake_leaders = [
    {"proxyWallet": f"0xAA{i}", "userName": f"trader{i}", "pnl": 1000000 - i, "vol": 1, "rank": i + 1}
    for i in range(5)
]
# trader1 : 100% sports (disqualifié), les autres 0%
def fake_activity(address, since_ts=None, limit=100, trade_type="TRADE", side="BUY"):
    if address == "0xAA1":
        return [{"title": "Lakers vs. Celtics", "timestamp": 999}] * 10
    return [{"title": "Will X win the election?", "timestamp": 999}] * 3

tf.get_leaderboard = lambda **kw: fake_leaders
tf.get_user_activity = fake_activity
cb.get_user_activity = fake_activity

traders = get_top_traders(3)
assert [t["username"] for t in traders] == ["trader0", "trader2", "trader3"], traders
print("Top 3 qualifiés OK (trader1 disqualifié ratio sports 100%)")

# refresh_traders : état complet + sizing par trader
state = cb._default_state()
cb.refresh_traders(state)
assert len(state["traders"]) == 3
for t in state["traders"]:
    assert t["address"] and t["username"]
    assert t["estimated_daily_trades"] == 3
    assert abs(t["trade_size_pct"] - 0.02) < 1e-9  # (15%/3)/3 = 1.67% -> plancher 2%
print("refresh_traders OK :", ", ".join(t["username"] for t in state["traders"]))
print("TOUS LES TESTS PASSENT")
