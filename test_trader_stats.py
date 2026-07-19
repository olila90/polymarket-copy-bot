"""Test : slippage enregistré au BUY, attribution conservée à la clôture, agrégation par trader."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import virtual.portfolio as pm

pf = {"initial_balance": 1000.0, "cash": 1000.0, "positions": {}, "trade_history": []}

# Trader A : 2 achats (slippage +2c et +4c), 1 WIN, 1 position ouverte
assert pm.paper_buy(pf, "tokA1", "Marché A1", "Yes", price=0.52, amount_usdc=20,
                    copied_from="0xA", condition_id="c1", trader_price=0.50)
assert pm.paper_buy(pf, "tokA2", "Marché A2", "No", price=0.94, amount_usdc=20,
                    copied_from="0xA", condition_id="c2", trader_price=0.90)
res = pm.paper_close(pf, "tokA1", won=True)
assert res["pnl"] > 0

# Trader B : 1 achat sans trader_price (ancien format), 1 SELL perdant
assert pm.paper_buy(pf, "tokB1", "Marché B1", "Yes", price=0.40, amount_usdc=20,
                    copied_from="0xB", condition_id="c3")
res = pm.paper_sell(pf, "tokB1", current_price=0.30)
assert res["pnl"] < 0

# Attribution conservée à la clôture
closes = [t for t in pf["trade_history"] if t["action"] in ("WIN", "LOSS", "SELL")]
assert all(t["copied_from"] for t in closes), closes
print("Attribution clôtures OK")

# Slippage enregistré
buys_a = [t for t in pf["trade_history"] if t["action"] == "BUY" and t["copied_from"] == "0xA"]
assert [t["slippage"] for t in buys_a] == [0.02, 0.04]
print("Slippage OK")

# Agrégation
stats = {s["address"]: s for s in pm.get_stats_by_trader(pf, prices={"tokA2": 0.95})}
a, b = stats["0xA"], stats["0xB"]
assert a["n_buys"] == 2 and a["wins"] == 1 and a["losses"] == 0
assert abs(a["avg_slippage"] - 0.03) < 1e-9
assert a["realized_pnl"] > 0
assert abs(a["unrealized_pnl"] - (20 / 0.94 * 0.95 - 20)) < 1e-3  # arrondi 4 décimales
assert b["n_buys"] == 1 and b["avg_slippage"] is None
assert abs(b["realized_pnl"] - (-5.0)) < 1e-6  # 50 shares × 0.30 - 20 = -5
assert stats["0xA"]["total_pnl"] > stats["0xB"]["total_pnl"]
print("Stats par trader OK")
print("TOUS LES TESTS PASSENT")
