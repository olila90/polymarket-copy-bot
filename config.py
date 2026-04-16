INITIAL_BALANCE = 1000.0        # USDC virtuels au démarrage
MAX_POSITION_SIZE_PCT = 0.20    # Max 20% du portfolio sur un seul marché
POLLING_INTERVAL_SEC = 60       # Fréquence vérification activité trader
LEADERBOARD_REFRESH_SEC = 3600  # Refresh top trader toutes les heures
LEADERBOARD_PERIOD = "MONTH"    # DAY / WEEK / MONTH / ALL
LEADERBOARD_METRIC = "PNL"      # PNL ou VOL
MIN_TRADE_USD = 5               # Ignorer trades originaux < $5
MAX_TRADE_AGE_H = 6             # Ignorer trades de plus de 6h (évite vieux historiques)

# Sizing dynamique : budget_journalier / nb_trades_estimés
DAILY_BUDGET_PCT = 0.80         # 80% du portfolio à déployer par jour max
MIN_TRADE_SIZE_PCT = 0.02       # Plancher : 2% par trade (si trader très actif)
MAX_TRADE_SIZE_PCT = 0.25       # Plafond  : 25% par trade (si trader peu actif)
TRADE_FREQ_WINDOW_H = 24        # Fenêtre pour estimer la fréquence du trader
MAX_LOGS = 100                  # Nombre max de lignes dans bot_state logs

DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
