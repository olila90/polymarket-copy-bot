#!/bin/bash
# Lance le bot en arrière-plan puis le dashboard Streamlit
echo "Starting Polymarket Copy Bot..."
python bot/copy_bot.py &

echo "Starting Streamlit dashboard..."
streamlit run dashboard/app.py \
  --server.address 0.0.0.0 \
  --server.port ${PORT:-8501} \
  --server.headless true \
  --browser.gatherUsageStats false
