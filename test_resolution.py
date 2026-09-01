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
    # Marchés absents de Gamma (archivés) → fallback CLOB
    "tok_clob_win":  None,
    "tok_clob_loss": None,
    "tok_clob_unsettled": None,
    "tok_gone": None,
}
# CLOB /markets/{condition_id} : source canonique quand Gamma a archivé le marché
CLOB_MARKETS = {
    "c_tok_clob_win":  {"condition_id": "c_tok_clob_win", "closed": True, "tokens": [
        {"token_id": "tok_clob_win", "outcome": "Yes", "winner": True},
        {"token_id": "tok_other", "outcome": "No", "winner": False}]},
    "c_tok_clob_loss": {"condition_id": "c_tok_clob_loss", "closed": True, "tokens": [
        {"token_id": "tok_clob_loss", "outcome": "Yes", "winner": False},
        {"token_id": "tok_other", "outcome": "No", "winner": True}]},
    # Fermé mais aucun winner désigné → pas encore réglé
    "c_tok_clob_unsettled": {"condition_id": "c_tok_clob_unsettled", "closed": True, "tokens": [
        {"token_id": "tok_clob_unsettled", "outcome": "Yes", "winner": False},
        {"token_id": "tok_other", "outcome": "No", "winner": False}]},
}
rm.get_market_by_token = lambda tid: MARKETS.get(tid)
rm.get_clob_market = lambda cid: CLOB_MARKETS.get(cid)

positions = {
    tid: {"condition_id": f"c_{tid}", "market_title": f"M {tid}", "outcome": "No",
          "shares": 10, "avg_price": 0.5, "cost_basis": 5, "copied_from": "0xMM"}
    for tid in MARKETS
}

resolved = {r["token_id"]: r for r in rm.check_resolutions(positions)}
assert set(resolved) == {"tok_win", "tok_loss", "tok_clob_win", "tok_clob_loss"}, resolved
assert resolved["tok_win"]["won"] is True
assert resolved["tok_loss"]["won"] is False
assert resolved["tok_clob_win"]["won"] is True
assert resolved["tok_clob_loss"]["won"] is False
print("Résolution par prix final du token OK")
print("Fallback CLOB winner (marchés archivés par Gamma) OK")
print("tok_open / tok_mid / tok_clob_unsettled / tok_gone correctement ignorés")
print("TOUS LES TESTS PASSENT")
