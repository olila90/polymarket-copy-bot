"""
Portfolio virtuel (paper trading).
Persiste l'état dans data/portfolio.json.
"""
import json
import time
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


def _default_portfolio(initial_balance: float) -> dict:
    return {
        "initial_balance": initial_balance,
        "cash": initial_balance,
        "positions": {},
        "trade_history": [],
    }


def load(initial_balance: float = 1000.0) -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    p = _default_portfolio(initial_balance)
    save(p)
    return p


def save(portfolio: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    tmp = str(PORTFOLIO_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(portfolio, f, indent=2)
    os.replace(tmp, PORTFOLIO_FILE)


def paper_buy(
    portfolio: dict,
    token_id: str,
    market_title: str,
    outcome: str,
    price: float,
    amount_usdc: float,
    copied_from: str = "",
    condition_id: str = "",
    trader_price: float | None = None,
) -> bool:
    """
    Simule un achat.
    amount_usdc : montant en USDC à dépenser.
    Retourne True si le trade a été exécuté.
    """
    if price <= 0 or price >= 1:
        return False
    if amount_usdc > portfolio["cash"]:
        amount_usdc = portfolio["cash"]
    if amount_usdc < 1:
        return False

    shares = amount_usdc / price

    # Mise à jour ou création de la position
    pos = portfolio["positions"]
    if token_id in pos:
        existing = pos[token_id]
        total_shares = existing["shares"] + shares
        total_cost = existing["cost_basis"] + amount_usdc
        existing["shares"] = total_shares
        existing["avg_price"] = total_cost / total_shares
        existing["cost_basis"] = total_cost
    else:
        pos[token_id] = {
            "condition_id": condition_id,
            "market_title": market_title,
            "outcome": outcome,
            "shares": shares,
            "avg_price": price,
            "cost_basis": amount_usdc,
            "opened_at": int(time.time()),
            "copied_from": copied_from,
        }

    portfolio["cash"] -= amount_usdc

    entry = {
        "ts": int(time.time()),
        "market_title": market_title,
        "outcome": outcome,
        "action": "BUY",
        "token_id": token_id,
        "shares": round(shares, 4),
        "price": price,
        "cost": round(amount_usdc, 4),
        "copied_from": copied_from,
    }
    if trader_price is not None and trader_price > 0:
        entry["trader_price"] = trader_price
        # Slippage : ce qu'on paie en plus (en cents) par rapport au prix du trader
        entry["slippage"] = round(price - trader_price, 4)
    portfolio["trade_history"].append(entry)

    return True


def get_total_value(portfolio: dict, prices: dict) -> float:
    """
    Valeur totale = cash + mark-to-market des positions.
    prices : dict {token_id: current_price}
    """
    total = portfolio["cash"]
    for token_id, pos in portfolio["positions"].items():
        current_price = prices.get(token_id, pos["avg_price"])
        total += pos["shares"] * current_price
    return total


def get_pnl_pct(portfolio: dict, prices: dict) -> float:
    """P&L en % par rapport au capital initial."""
    initial = portfolio["initial_balance"]
    current = get_total_value(portfolio, prices)
    return (current - initial) / initial * 100


def paper_close(portfolio: dict, token_id: str, won: bool) -> dict | None:
    """
    Ferme une position résolue.
    won=True  → encaisse shares × $1.00
    won=False → encaisse $0 (perte totale)
    Retourne le résumé de la clôture, ou None si position inexistante.
    """
    pos = portfolio["positions"].get(token_id)
    if pos is None:
        return None

    payout = pos["shares"] * 1.0 if won else 0.0
    pnl = payout - pos["cost_basis"]

    portfolio["cash"] += payout
    del portfolio["positions"][token_id]

    portfolio["trade_history"].append({
        "ts": int(time.time()),
        "market_title": pos["market_title"],
        "outcome": pos["outcome"],
        "action": "WIN" if won else "LOSS",
        "token_id": token_id,
        "shares": round(pos["shares"], 4),
        "price": 1.0 if won else 0.0,
        "cost": round(payout, 4),
        "copied_from": pos.get("copied_from", ""),
        "pnl": round(pnl, 4),
    })

    return {
        "market_title": pos["market_title"],
        "outcome": pos["outcome"],
        "won": won,
        "payout": payout,
        "cost_basis": pos["cost_basis"],
        "pnl": pnl,
    }


def paper_sell(portfolio: dict, token_id: str, current_price: float) -> dict | None:
    """Ferme une position à prix marché (copie d'un SELL du trader suivi)."""
    pos = portfolio["positions"].get(token_id)
    if pos is None:
        return None

    payout = pos["shares"] * current_price
    pnl = payout - pos["cost_basis"]

    portfolio["cash"] += payout
    del portfolio["positions"][token_id]

    portfolio["trade_history"].append({
        "ts": int(time.time()),
        "market_title": pos["market_title"],
        "outcome": pos["outcome"],
        "action": "SELL",
        "token_id": token_id,
        "shares": round(pos["shares"], 4),
        "price": current_price,
        "cost": round(payout, 4),
        "copied_from": pos.get("copied_from", ""),
        "pnl": round(pnl, 4),
    })

    return {
        "market_title": pos["market_title"],
        "outcome": pos["outcome"],
        "price": current_price,
        "payout": payout,
        "cost_basis": pos["cost_basis"],
        "pnl": pnl,
    }


def get_stats_by_trader(portfolio: dict, prices: dict) -> list[dict]:
    """
    Agrège l'historique et les positions ouvertes par trader copié.
    Retourne une ligne par adresse :
      {address, n_buys, invested, realized_pnl, unrealized_pnl, total_pnl,
       wins, losses, avg_slippage (None si aucun BUY avec trader_price)}
    """
    stats: dict[str, dict] = {}

    def row(address: str) -> dict:
        if address not in stats:
            stats[address] = {
                "address": address,
                "n_buys": 0, "invested": 0.0,
                "realized_pnl": 0.0, "unrealized_pnl": 0.0,
                "wins": 0, "losses": 0,
                "_slippages": [],
            }
        return stats[address]

    for t in portfolio["trade_history"]:
        addr = t.get("copied_from", "")
        if not addr:
            continue
        r = row(addr)
        action = t.get("action", "")
        if action == "BUY":
            r["n_buys"] += 1
            r["invested"] += t.get("cost", 0)
            if "slippage" in t:
                r["_slippages"].append(t["slippage"])
        elif action in ("SELL", "WIN", "LOSS"):
            r["realized_pnl"] += t.get("pnl", 0)
            if action == "WIN":
                r["wins"] += 1
            elif action == "LOSS":
                r["losses"] += 1

    for token_id, pos in portfolio["positions"].items():
        addr = pos.get("copied_from", "")
        if not addr:
            continue
        r = row(addr)
        current_price = prices.get(token_id, pos["avg_price"])
        r["unrealized_pnl"] += pos["shares"] * current_price - pos["cost_basis"]

    result = []
    for r in stats.values():
        slippages = r.pop("_slippages")
        r["avg_slippage"] = round(sum(slippages) / len(slippages), 4) if slippages else None
        r["total_pnl"] = round(r["realized_pnl"] + r["unrealized_pnl"], 4)
        r["realized_pnl"] = round(r["realized_pnl"], 4)
        r["unrealized_pnl"] = round(r["unrealized_pnl"], 4)
        r["invested"] = round(r["invested"], 4)
        result.append(r)

    return sorted(result, key=lambda x: x["total_pnl"], reverse=True)


def get_positions_with_pnl(portfolio: dict, prices: dict) -> list[dict]:
    """Liste des positions enrichies avec prix actuel et P&L."""
    result = []
    for token_id, pos in portfolio["positions"].items():
        current_price = prices.get(token_id, pos["avg_price"])
        current_value = pos["shares"] * current_price
        pnl = current_value - pos["cost_basis"]
        pnl_pct = pnl / pos["cost_basis"] * 100 if pos["cost_basis"] > 0 else 0
        result.append({
            **pos,
            "token_id": token_id,
            "current_price": current_price,
            "current_value": round(current_value, 4),
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
        })
    return sorted(result, key=lambda x: x["opened_at"], reverse=True)
