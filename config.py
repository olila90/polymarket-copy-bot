INITIAL_BALANCE = 1000.0        # USDC virtuels au démarrage
MAX_POSITION_SIZE_PCT = 0.05    # Max 5% du portfolio par condition_id (match/événement)
POLLING_INTERVAL_SEC = 60       # Fréquence vérification activité trader
LEADERBOARD_REFRESH_SEC = 3600  # Refresh top traders toutes les heures
TOP_N_TRADERS = 3               # Nombre de traders suivis simultanément (diversification)
LEADERBOARD_PERIOD = "MONTH"    # DAY / WEEK / MONTH / ALL
LEADERBOARD_METRIC = "PNL"      # PNL ou VOL
MIN_TRADE_USD = 5               # Ignorer trades originaux < $5
MAX_TRADE_AGE_H = 0.5           # Ignorer trades > 30min

# Sizing dynamique : budget_journalier / nb_trades_estimés
DAILY_BUDGET_PCT = 0.15         # 15% du portfolio à déployer par jour max (council: réduit de 80%→15%)
MIN_TRADE_SIZE_PCT = 0.02       # Plancher : 2% par trade
MAX_TRADE_SIZE_PCT = 0.05       # Plafond  : 5% par trade (aligné sur MAX_POSITION_SIZE_PCT)
TRADE_FREQ_WINDOW_H = 24        # Fenêtre pour estimer la fréquence du trader
MAX_LOGS = 100                  # Nombre max de lignes dans bot_state logs

# Garde-fous (council v2)
STOP_LOSS_PCT = 0.25            # Suspendre si portfolio < capital initial × (1 - 0.25)
MAX_SEEN_TX_HASHES = 2000       # Taille max du set de déduplication tx_hash
MAX_OPEN_POSITIONS = 6          # Nombre max de positions ouvertes simultanées
CONDITION_COOLDOWN_H = 4        # Cooldown entre deux achats sur le même condition_id
MAX_SPORTS_RATIO = 0.60         # Rejeter un trader si >60% de ses trades sont des paris sportifs courts

# Garde-fous v3 (post-gel du 28/07→01/09 : 6 positions swisstony bloquées 5 semaines)
MAX_HOLD_DAYS = 7               # Sortie forcée (prix marché) des positions plus vieilles
MAX_POSITIONS_PER_TRADER = 2    # Un seul trader ne peut pas remplir le book
MAX_TRADER_DAILY_TRADES = 25    # Rejeter les market makers hyperactifs (non copiables)

# Paris de ligne purs (50/50 par construction, edge non copiable) — exclus par trade
LINE_BET_KEYWORDS = (
    "O/U", "Spread:", "Over/Under", "Total:", "Moneyline",
    "Exact Score", "end in a draw",
)
# Motifs regex équivalents : "Will X win on 2026-07-28?" = moneyline déguisée
LINE_BET_PATTERNS = (
    r"\bwin on \d{4}-\d{2}-\d{2}",
)
# Liste sports complète — sert uniquement à calculer le ratio sports d'un trader
# (qualification). Les marchés sportifs hors paris de ligne SONT copiés.
SPORTS_KEYWORDS = LINE_BET_KEYWORDS + (
    " vs. ",
    "NBA", "NFL", "NHL", "MLB", "NCAA", "MLS", "WNBA",
    " Finals", "Super Bowl", "World Series", "Grand Prix",
)

DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
