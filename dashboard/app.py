"""
Dashboard Streamlit — Polymarket Copy Bot (Paper Trading)
Lancer : streamlit run dashboard/app.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

from api.clob_api import get_midpoints_batch
from bot.trader_finder import get_leaderboard_top10, get_top_trader
import virtual.portfolio as portfolio_mod
from config import INITIAL_BALANCE, LEADERBOARD_PERIOD, LEADERBOARD_METRIC

DATA_DIR = Path(__file__).parent.parent / "data"
BOT_STATE_FILE = DATA_DIR / "bot_state.json"


# ── Cache API ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def cached_midpoints(token_ids_tuple: tuple) -> dict:
    return get_midpoints_batch(list(token_ids_tuple))

@st.cache_data(ttl=300)
def cached_leaderboard() -> list:
    return get_leaderboard_top10()


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_bot_state() -> dict:
    if BOT_STATE_FILE.exists():
        try:
            with open(BOT_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def fmt_usdc(v: float) -> str:
    return f"${v:,.2f}"

def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"

def time_ago(ts: int) -> str:
    if not ts:
        return "—"
    delta = int(time.time()) - ts
    if delta < 60:
        return f"{delta}s ago"
    elif delta < 3600:
        return f"{delta // 60}min ago"
    elif delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="POLYBOT // COPY TRADING",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── FUTURISTIC DARK THEME CSS ─────────────────────────────────────────────────

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">

<style>
/* ── ROOT VARIABLES ── */
:root {
    --bg-void:      #05050a;
    --bg-deep:      #080810;
    --bg-card:      #0c0c18;
    --bg-card2:     #0f0f1e;
    --cyan:         #00e5ff;
    --cyan-dim:     #00a8cc;
    --cyan-glow:    rgba(0, 229, 255, 0.15);
    --cyan-glow2:   rgba(0, 229, 255, 0.06);
    --green:        #00ff88;
    --green-dim:    #00cc6a;
    --red:          #ff3860;
    --red-dim:      #cc2d4d;
    --text-primary: #e0f7ff;
    --text-dim:     #6a8a9a;
    --text-muted:   #3a5060;
    --border:       rgba(0, 229, 255, 0.18);
    --border-bright:rgba(0, 229, 255, 0.45);
    --font-head:    'Orbitron', monospace;
    --font-mono:    'Share Tech Mono', monospace;
}

/* ── GLOBAL RESET ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], .main, .block-container {
    background-color: var(--bg-void) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-mono) !important;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(0,229,255,0.07) 0%, transparent 70%),
        var(--bg-void) !important;
}

.block-container {
    padding-top: 2rem !important;
    max-width: 1400px !important;
}

/* Hide default Streamlit elements */
#MainMenu, footer, header, [data-testid="stToolbar"],
[data-testid="collapsedControl"] { display: none !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-deep); }
::-webkit-scrollbar-thumb { background: var(--cyan-dim); border-radius: 2px; }

/* ── TITLE / HEADERS ── */
h1 {
    font-family: var(--font-head) !important;
    font-size: 1.6rem !important;
    font-weight: 900 !important;
    color: var(--cyan) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    text-shadow: 0 0 30px rgba(0,229,255,0.6), 0 0 60px rgba(0,229,255,0.2) !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}

h2, h3 {
    font-family: var(--font-head) !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-size: 0.85rem !important;
}

/* ── CAPTION / TEXT ── */
[data-testid="stCaptionContainer"] p,
.stCaption, small {
    font-family: var(--font-mono) !important;
    color: var(--text-dim) !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.04em !important;
}

p, li, span, div {
    font-family: var(--font-mono) !important;
}

/* ── DIVIDER ── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.2rem 0 !important;
    box-shadow: 0 0 8px var(--cyan-glow) !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-card2) 100%) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    padding: 1.1rem 1.2rem !important;
    box-shadow:
        0 0 0 1px rgba(0,229,255,0.05),
        0 4px 24px rgba(0,0,0,0.6),
        inset 0 1px 0 rgba(0,229,255,0.08) !important;
    position: relative !important;
    overflow: hidden !important;
    transition: border-color 0.3s, box-shadow 0.3s !important;
}

[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
    opacity: 0.6;
}

[data-testid="stMetric"]:hover {
    border-color: var(--border-bright) !important;
    box-shadow:
        0 0 20px var(--cyan-glow),
        0 4px 24px rgba(0,0,0,0.6),
        inset 0 1px 0 rgba(0,229,255,0.12) !important;
}

[data-testid="stMetricLabel"] {
    font-family: var(--font-mono) !important;
    font-size: 0.68rem !important;
    color: var(--text-dim) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}

[data-testid="stMetricValue"] {
    font-family: var(--font-head) !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    color: var(--cyan) !important;
    text-shadow: 0 0 20px rgba(0,229,255,0.5) !important;
    letter-spacing: 0.04em !important;
}

[data-testid="stMetricDelta"] {
    font-family: var(--font-mono) !important;
    font-size: 0.8rem !important;
}

[data-testid="stMetricDelta"] [data-testid="stMetricDeltaIcon-Up"] ~ div,
[data-testid="stMetricDelta"] svg + div {
    color: var(--green) !important;
}

/* ── TABS ── */
[data-testid="stTabs"] {
    border-bottom: 1px solid var(--border) !important;
}

[data-testid="stTab"] {
    font-family: var(--font-head) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: var(--text-dim) !important;
    border: none !important;
    background: transparent !important;
    padding: 0.6rem 1.2rem !important;
    transition: color 0.2s !important;
}

[data-testid="stTab"]:hover {
    color: var(--cyan) !important;
}

[data-testid="stTab"][aria-selected="true"] {
    color: var(--cyan) !important;
    border-bottom: 2px solid var(--cyan) !important;
    text-shadow: 0 0 12px rgba(0,229,255,0.6) !important;
    background: transparent !important;
}

/* ── DATAFRAME / TABLE ── */
[data-testid="stDataFrame"], .stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    overflow: hidden !important;
    box-shadow: 0 0 30px rgba(0,0,0,0.5) !important;
}

[data-testid="stDataFrame"] iframe {
    background: var(--bg-card) !important;
}

/* Glitch line effect on table top */
[data-testid="stDataFrame"]::before {
    content: '';
    display: block;
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, var(--cyan) 40%, var(--green) 60%, transparent 100%);
    opacity: 0.7;
}

/* ── BUTTON ── */
[data-testid="stButton"] > button {
    font-family: var(--font-head) !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: var(--bg-void) !important;
    background: linear-gradient(135deg, var(--cyan) 0%, var(--cyan-dim) 100%) !important;
    border: none !important;
    border-radius: 2px !important;
    padding: 0.5rem 1.4rem !important;
    box-shadow:
        0 0 20px rgba(0,229,255,0.4),
        0 0 40px rgba(0,229,255,0.1) !important;
    transition: all 0.2s !important;
    cursor: pointer !important;
}

[data-testid="stButton"] > button:hover {
    box-shadow:
        0 0 30px rgba(0,229,255,0.7),
        0 0 60px rgba(0,229,255,0.2) !important;
    transform: translateY(-1px) !important;
}

[data-testid="stButton"] > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 0 15px rgba(0,229,255,0.4) !important;
}

/* ── TEXT AREA (LOGS) ── */
[data-testid="stTextArea"] textarea {
    font-family: var(--font-mono) !important;
    font-size: 0.72rem !important;
    background: var(--bg-card) !important;
    color: var(--green) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 10px var(--cyan-glow2) !important;
    caret-color: var(--cyan) !important;
    line-height: 1.6 !important;
}

[data-testid="stTextArea"] textarea:focus {
    border-color: var(--border-bright) !important;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 15px var(--cyan-glow) !important;
    outline: none !important;
}

/* ── CODE BLOCK ── */
[data-testid="stCode"], .stCode {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}

code {
    font-family: var(--font-mono) !important;
    color: var(--cyan-dim) !important;
    font-size: 0.75rem !important;
    background: transparent !important;
}

/* ── ALERTS ── */
[data-testid="stAlert"] {
    border-radius: 4px !important;
    border-left-width: 3px !important;
    background: var(--bg-card) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.8rem !important;
}

[data-testid="stAlert"][data-baseweb="notification"] {
    background: rgba(0, 229, 255, 0.05) !important;
    border-left-color: var(--cyan) !important;
    color: var(--text-primary) !important;
}

.stSuccess {
    background: rgba(0, 255, 136, 0.06) !important;
    border-left-color: var(--green) !important;
    color: var(--green) !important;
}

.stError, [data-testid="stAlert"].stError {
    background: rgba(255, 56, 96, 0.06) !important;
    border-left-color: var(--red) !important;
    color: var(--red) !important;
}

.stWarning {
    background: rgba(255, 200, 0, 0.05) !important;
    border-left-color: #ffc800 !important;
    color: #ffc800 !important;
}

.stInfo {
    background: rgba(0, 229, 255, 0.05) !important;
    border-left-color: var(--cyan) !important;
    color: var(--text-dim) !important;
}

/* ── SPINNER ── */
[data-testid="stSpinner"] {
    color: var(--cyan) !important;
}

/* ── COLUMNS ── */
[data-testid="column"] {
    padding: 0 0.4rem !important;
}

/* ── SUBHEADER decoration ── */
h3::before {
    content: '// ';
    color: var(--cyan);
    opacity: 0.5;
}

/* ── CUSTOM HEADER PANEL ── */
.header-panel {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(135deg, var(--bg-card) 0%, rgba(0,229,255,0.03) 100%);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.8rem 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 0 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(0,229,255,0.06);
}

.header-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
}

.header-stat-label {
    font-size: 0.6rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.header-stat-value {
    font-family: var(--font-head);
    font-size: 0.85rem;
    color: var(--cyan);
    font-weight: 600;
}

/* ── PULSE DOT ── */
.pulse-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 6px var(--green), 0 0 12px var(--green);
    animation: pulse 2s ease-in-out infinite;
    margin-right: 6px;
    vertical-align: middle;
}

@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 6px var(--green), 0 0 12px var(--green); }
    50%       { opacity: 0.4; box-shadow: 0 0 2px var(--green); }
}

/* ── SCAN LINE effect on page ── */
[data-testid="stAppViewContainer"]::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,0,0,0.03) 2px,
        rgba(0,0,0,0.03) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

/* ── CORNER DECORATION ── */
.corner-box {
    position: relative;
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-card2) 100%);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}

.corner-box::before, .corner-box::after {
    content: '';
    position: absolute;
    width: 10px;
    height: 10px;
    border-color: var(--cyan);
    border-style: solid;
    opacity: 0.7;
}

.corner-box::before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.corner-box::after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }

/* ── TICKER ── */
.status-ticker {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--text-dim);
    letter-spacing: 0.05em;
    padding: 0.3rem 0;
}

.status-ticker .highlight { color: var(--cyan); }
.status-ticker .positive  { color: var(--green); }
.status-ticker .negative  { color: var(--red); }
.status-ticker .sep       { color: var(--text-muted); margin: 0 0.5rem; }

/* ── LEADERBOARD RANK ── */
.rank-1 { color: #ffd700 !important; text-shadow: 0 0 10px rgba(255,215,0,0.5); }
.rank-2 { color: #c0c0c0 !important; }
.rank-3 { color: #cd7f32 !important; }
</style>
""", unsafe_allow_html=True)


# ── DATA LOAD ─────────────────────────────────────────────────────────────────

state = load_bot_state()
pf = portfolio_mod.load(INITIAL_BALANCE)

trader_name = state.get("trader_username") or "—"
last_check = time_ago(state.get("last_activity_check", 0))
n_trades = state.get("total_trades_copied", 0)
bot_active = bool(state.get("current_trader"))


# ── HEADER ────────────────────────────────────────────────────────────────────

token_ids = tuple(pf["positions"].keys())
prices = cached_midpoints(token_ids) if token_ids else {}
total_value = portfolio_mod.get_total_value(pf, prices)
pnl_pct = portfolio_mod.get_pnl_pct(pf, prices)
pnl_abs = total_value - pf["initial_balance"]
pnl_color = "positive" if pnl_abs >= 0 else "negative"
pnl_sign = "+" if pnl_abs >= 0 else ""

pulse_color = "#00ff88" if bot_active else "#ff3860"

st.markdown(f"""
<div style="display:flex; align-items:baseline; gap:1rem; margin-bottom:0.3rem;">
  <h1 style="margin:0;padding:0;">⬡ POLYBOT</h1>
  <span style="font-family:'Orbitron',monospace; font-size:0.65rem; color:var(--text-muted); letter-spacing:0.15em; text-transform:uppercase; margin-top:0.5rem;">
    // COPY TRADING SYSTEM v1.0
  </span>
</div>
<div class="status-ticker">
  <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{pulse_color};
    box-shadow:0 0 6px {pulse_color};animation:pulse 2s infinite;vertical-align:middle;margin-right:6px;"></span>
  <span class="highlight">TRACKING</span>
  <span class="sep">|</span>
  {trader_name[:30]}
  <span class="sep">·</span>
  LAST SYNC <span class="highlight">{last_check}</span>
  <span class="sep">·</span>
  TRADES COPIED <span class="positive">{n_trades}</span>
  <span class="sep">·</span>
  CAPITAL <span class="highlight">{fmt_usdc(INITIAL_BALANCE)}</span>
  <span class="sep">·</span>
  P&amp;L <span class="{pnl_color}">{pnl_sign}{fmt_usdc(pnl_abs)} ({pnl_sign}{pnl_pct:.2f}%)</span>
</div>
""", unsafe_allow_html=True)

col_refresh, _ = st.columns([1, 8])
if col_refresh.button("⟳  REFRESH"):
    st.cache_data.clear()
    st.rerun()

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "▣  PORTFOLIO",
    "≡  HISTORIQUE",
    "◈  LEADERBOARD",
    "◎  BOT STATUS",
])


# ── TAB 1 : PORTFOLIO ─────────────────────────────────────────────────────────

with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("BALANCE TOTALE",   fmt_usdc(total_value), fmt_pct(pnl_pct))
    col2.metric("CASH DISPONIBLE",  fmt_usdc(pf["cash"]))
    col3.metric("P&L ABSOLU",       f"{pnl_sign}{fmt_usdc(pnl_abs)}")
    col4.metric("POSITIONS",        str(len(pf["positions"])))

    st.divider()

    if pf["positions"]:
        st.subheader("Positions ouvertes")
        rows = portfolio_mod.get_positions_with_pnl(pf, prices)
        df = pd.DataFrame(rows)

        display_cols = {
            "market_title": "MARCHÉ",
            "outcome":      "OUTCOME",
            "shares":       "SHARES",
            "avg_price":    "ENTRÉE",
            "current_price":"ACTUEL",
            "cost_basis":   "INVESTI",
            "current_value":"VALEUR",
            "pnl":          "P&L $",
            "pnl_pct":      "P&L %",
        }
        df_display = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)

        for col in ["ENTRÉE", "ACTUEL"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].map(lambda x: f"{x:.3f}")
        for col in ["INVESTI", "VALEUR", "P&L $"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].map(lambda x: f"${x:.2f}")
        if "P&L %" in df_display.columns:
            df_display["P&L %"] = df_display["P&L %"].map(lambda x: fmt_pct(x))

        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("// NO OPEN POSITIONS — Lance `python bot/copy_bot.py` pour démarrer le copy trading.")


# ── TAB 2 : HISTORIQUE ────────────────────────────────────────────────────────

with tab2:
    history = pf.get("trade_history", [])

    if history:
        st.subheader(f"Trade log — {len(history)} exécutions")
        rows = []
        for t in reversed(history):
            copied_from = t.get("copied_from", "")
            rows.append({
                "TIMESTAMP":   datetime.fromtimestamp(t["ts"]).strftime("%m/%d %H:%M"),
                "MARCHÉ":      t.get("market_title", "")[:55],
                "OUTCOME":     t.get("outcome", ""),
                "SHARES":      f"{t.get('shares', 0):.2f}",
                "PRIX":        f"{t.get('price', 0):.3f}",
                "USDC":        f"${t.get('cost', 0):.2f}",
                "COPIÉ DE":    (copied_from[:10] + "…") if copied_from else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("// NO TRADE HISTORY — Aucun trade copié pour l'instant.")


# ── TAB 3 : LEADERBOARD ───────────────────────────────────────────────────────

with tab3:
    current_trader = state.get("current_trader", "")
    last_lb = time_ago(state.get("last_leaderboard_refresh", 0))

    st.subheader(f"Top traders — {LEADERBOARD_PERIOD} / {LEADERBOARD_METRIC}")
    st.markdown(f"<div class='status-ticker'>Cache 5min · Dernier refresh <span class='highlight'>{last_lb}</span></div>", unsafe_allow_html=True)

    leaders = cached_leaderboard()

    if leaders:
        rows = []
        for t in leaders:
            is_current = t["address"] == current_trader
            rows.append({
                "RANG":     f"{'★ ' if is_current else ''}#{t['rank']}",
                "USERNAME": t["username"][:25],
                "PNL":      f"${t['pnl']:,.0f}",
                "VOLUME":   f"${t['volume']:,.0f}",
                "TWITTER":  f"@{t['x_username']}" if t.get("x_username") else "—",
                "WALLET":   t["address"][:10] + "…",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("<div class='status-ticker'><span class='highlight'>★</span> = trader actuellement copié par le bot</div>", unsafe_allow_html=True)
    else:
        st.error("// ERROR — Impossible de charger le leaderboard.")


# ── TAB 4 : BOT STATUS ────────────────────────────────────────────────────────

with tab4:
    if not state:
        st.warning("// BOT OFFLINE — Exécute `python bot/copy_bot.py` pour démarrer.")
    else:
        trader_pnl  = state.get("trader_pnl", 0)
        trader_addr = state.get("current_trader") or "—"

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Trader ciblé")
            pulse = "#00ff88" if bot_active else "#ff3860"
            st.markdown(f"""
            <div class="corner-box">
              <div style="font-family:var(--font-head);font-size:0.9rem;color:var(--cyan);margin-bottom:0.3rem;">
                <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{pulse};
                  box-shadow:0 0 6px {pulse};animation:pulse 2s infinite;vertical-align:middle;margin-right:8px;"></span>
                {trader_name[:35]}
              </div>
              <div style="font-size:0.7rem;color:var(--text-dim);margin-bottom:0.5rem;">
                PNL MENSUEL: <span style="color:var(--green);font-family:var(--font-head);">${trader_pnl:,.0f}</span>
              </div>
              <div style="font-family:var(--font-mono);font-size:0.68rem;color:var(--text-muted);word-break:break-all;">
                {trader_addr}
              </div>
            </div>
            """, unsafe_allow_html=True)

            st.subheader("Métriques système")
            n_daily = state.get("estimated_daily_trades")
            trade_pct = state.get("dynamic_trade_size_pct")
            st.metric("TRADES COPIÉS",        state.get("total_trades_copied", 0))
            st.metric("DERNIER CHECK",         time_ago(state.get("last_activity_check", 0)))
            st.metric("REFRESH LEADERBOARD",   time_ago(state.get("last_leaderboard_refresh", 0)))
            if n_daily is not None:
                st.metric("TRADES/JOUR ESTIMÉS",  n_daily)
            if trade_pct is not None:
                st.metric("TAILLE PAR TRADE",  f"{trade_pct*100:.1f}% du portfolio")

        with col2:
            st.subheader("System log")
            logs = state.get("logs", [])
            if logs:
                st.text_area(
                    label="",
                    value="\n".join(reversed(logs[-20:])),
                    height=400,
                    disabled=True,
                )
            else:
                st.info("// NO LOGS")

        st.divider()
        col_reset, col_lb = st.columns(2)
        if col_reset.button("⚠  RESET P&L ($1 000)"):
            pf_reset = {
                "initial_balance": INITIAL_BALANCE,
                "cash": INITIAL_BALANCE,
                "positions": {},
                "trade_history": [],
            }
            portfolio_mod.save(pf_reset)
            state["total_trades_copied"] = 0
            state["seen_tx_hashes"] = []
            state["stop_loss_triggered"] = False
            state["last_activity_check"] = int(time.time())
            tmp = str(BOT_STATE_FILE) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, BOT_STATE_FILE)
            st.cache_data.clear()
            st.success("// P&L RESET → $1,000 USDC")
            st.rerun()

        if col_lb.button("⚡  FORCE LEADERBOARD REFRESH"):
            with st.spinner("Querying Polymarket API..."):
                trader = get_top_trader()
                if trader:
                    state["current_trader"]           = trader["address"]
                    state["trader_username"]           = trader["username"]
                    state["trader_pnl"]               = trader["pnl"]
                    state["last_leaderboard_refresh"]  = int(time.time())
                    tmp = str(BOT_STATE_FILE) + ".tmp"
                    with open(tmp, "w") as f:
                        json.dump(state, f, indent=2)
                    os.replace(tmp, BOT_STATE_FILE)
                    st.cache_data.clear()
                    st.success(f"// TARGET UPDATED → {trader['username']} // PNL ${trader['pnl']:,.0f}")
                    st.rerun()
                else:
                    st.error("// API ERROR — Impossible de récupérer le leaderboard.")

        # Afficher le statut stop-loss
        if state.get("stop_loss_triggered"):
            st.error("// ⚠ STOP-LOSS ACTIF — Trades suspendus. Réinitialise le P&L pour reprendre.")
