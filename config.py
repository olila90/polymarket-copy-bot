INITIAL_BALANCE = 1000.0        # USDC virtuels au démarrage
MAX_POSITION_SIZE_PCT = 0.05    # Max 5% du portfolio par condition_id (match/événement)
POLLING_INTERVAL_SEC = 60       # Fréquence vérification activité trader
LEADERBOARD_REFRESH_SEC = 3600  # Refresh top trader toutes les heures
LEADERBOARD_PERIOD = "DAY"      # DAY / WEEK / MONTH / ALL
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

DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
