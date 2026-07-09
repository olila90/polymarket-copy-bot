FROM python:3.12-slim

# Sans ça, stdout est bufferisé par blocs de 8KB dans le conteneur :
# les logs du bot n'apparaissent dans Railway qu'avec ~2 jours de retard.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data

EXPOSE 8501

# Boucle de relance : si le bot meurt, Streamlit garde le conteneur "healthy"
# et rien ne le relancerait sinon.
CMD (while true; do python -u bot/copy_bot.py; echo "[supervisor] copy_bot est mort (code $?), relance dans 30s"; sleep 30; done) & streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port ${PORT:-8501} --server.headless true --browser.gatherUsageStats false
