INITIAL_BALANCE = 1000.0        # USDC virtuels au démarrage
MAX_POSITION_SIZE_PCT = 0.05    # Max 5% du portfolio sur un seul marché (council: réduit de 20%→5%)
POLLING_INTERVAL_SEC = 60       # Fréquence vérification activité trader
LEADERBOARD_REFRESH_SEC = 3600  # Refresh top trader toutes les heures
LEADERBOARD_PERIOD = "MONTH"    # DAY / WEEK / MONTH / ALL
LEADERBOARD_METRIC = "PNL"      # PNL ou VOL
MIN_TRADE_USD = 5               # Ignorer trades originaux < $5
MAX_TRADE_AGE_H = 0.5           # Ignorer trades > 30min (council: réduit de 6h→0.5h)

# Sizing dynamique : budget_journalier / nb_trades_estimés
DAILY_BUDGET_PCT = 0.80         # 80% du portfolio à déployer par jour max
MIN_TRADE_SIZE_PCT = 0.02       # Plancher : 2% par trade (si trader très actif)
MAX_TRADE_SIZE_PCT = 0.10       # Plafond  : 10% par trade (council: réduit de 25%→10%)
TRADE_FREQ_WINDOW_H = 24        # Fenêtre pour estimer la fréquence du trader
MAX_LOGS = 100                  # Nombre max de lignes dans bot_state logs

# Garde-fous (council)
STOP_LOSS_PCT = 0.25            # Suspendre si portfolio < capital initial × (1 - 0.25)
MAX_SEEN_TX_HASHES = 2000       # Taille max du set de déduplication tx_hash

DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
