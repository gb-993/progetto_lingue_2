#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] DJANGO_DEBUG=${DJANGO_DEBUG:-0} SEED_ON_START=${SEED_ON_START:-false}"

# ---- Attendi il DB ----
echo "[entrypoint] waiting for Postgres ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until python - <<'PYCODE'
import os, sys, socket
host=os.environ.get("POSTGRES_HOST","db")
port=int(os.environ.get("POSTGRES_PORT","5432"))
with socket.socket() as s:
    try:
        s.settimeout(1.0)
        s.connect((host, port))
        sys.exit(0)
    except Exception:
        sys.exit(1)
PYCODE
do
  sleep 1
done
echo "[entrypoint] Postgres is up."

# ---- Migrazioni e statici ----
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# ---- Seed opzionale da CSV ----
SEED_FLAG="${SEED_ON_START:-false}"
if [ "${SEED_FLAG}" = "true" ] || [ "${SEED_FLAG}" = "1" ] || [ "${SEED_FLAG}" = "True" ] || [ "${SEED_FLAG}" = "TRUE" ]; then
  if [ -d "/app/data" ]; then
    echo "[entrypoint] Running seed_from_csv..."
    python manage.py seed_from_csv || { echo "[entrypoint] seed_from_csv failed"; exit 1; }
  else
    echo "[entrypoint] WARNING: /app/data non esiste, salto seed."
  fi
else
  echo "[entrypoint] SEED_ON_START disabilitato, salto seed."
fi

# ---- Health endpoint di cortesia (solo se non l'hai già) ----
# Se NON hai una view /health/, attiva il check interno di Django con runserver.
# Nginx healthcheck punta a / (homepage). Se hai già /health/, ignora questa nota.

# ---- Avvio server ----
if [ "${DJANGO_DEBUG:-0}" = "1" ]; then
  echo "[entrypoint] Starting Django runserver (dev)..."
  exec python manage.py runserver 0.0.0.0:8000
else
  echo "[entrypoint] Starting gunicorn (prod)..."
  exec gunicorn progetto_lingua_2.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
fi
