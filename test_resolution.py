"""Test : la résolution se base sur le prix final de NOTRE token, pas sur les REDEEM du trader."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import bot.resolution_monitor as rm

MARKETS = {
    # Notre token a gagné (prix final 1)
    "tok_win":  {"closed": True,  "clobTokenIds": '["tok_win", "tok_other"]',  "outcomePrices": '["1", "0"]'},
    # Notre token a perdu (prix final 0) — même si le trader copié a encaissé l'autre côté
    "tok_loss": {"closed": True,  "clobTokenIds": '["tok_loss", "tok_other"]', "outcomePrices": '["0", "1"]'},
    # Marché encore ouvert
    "tok_open": {"closed": False, "clobTokenIds": '["tok_open", "tok_other"]', "outcomePrices": '["0.6", "0.4"]'},
    # Fermé mais pas encore réglé (prix intermédiaire)
    "tok_mid":  {"closed": True,  "clobTokenIds": '["tok_mid", "tok_other"]',  "outcomePrices": '["0.6", "0.4"]'},
    # Marché introuvable
    "tok_gone": None,
}
rm.get_market_by_token = lambda tid: MARKETS.get(tid)

positions = {
    tid: {"condition_id": f"c_{tid}", "market_title": f"M {tid}", "outcome": "No",
          "shares": 10, "avg_price": 0.5, "cost_basis": 5, "copied_from": "0xMM"}
    for tid in MARKETS
}

resolved = {r["token_id"]: r for r in rm.check_resolutions(positions)}
assert set(resolved) == {"tok_win", "tok_loss"}, resolved
assert resolved["tok_win"]["won"] is True
assert resolved["tok_loss"]["won"] is False
print("Résolution par prix final du token OK")
print("tok_open / tok_mid / tok_gone correctement ignorés")
print("TOUS LES TESTS PASSENT")
