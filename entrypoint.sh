#!/bin/sh
set -e

APP_UID=1000
APP_GID=1000
APP_USER=appuser
APP_GROUP=appuser

MODE=${1:-gunicorn}

# Se siamo root: sistemiamo permessi volumi e poi ri-eseguiamo come appuser
if [ "$(id -u)" = "0" ]; then
  # Crea cartelle se mancano (volumi vuoti al primo run)
  mkdir -p /app/staticfiles /app/media

  # Imposta ownership e permessi sicuri (setgid per mantenere il gruppo)
  chown -R ${APP_UID}:${APP_GID} /app/staticfiles /app/media
  chmod -R g+rwX /app/staticfiles /app/media
  find /app/staticfiles /app/media -type d -exec chmod g+s {} \; || true

  # Re-exec come utente non-root con gosu, passando gli stessi argomenti
  exec gosu ${APP_USER}:${APP_GROUP} /app/entrypoint.sh "$MODE"
fi

# Da qui siamo non-root (appuser)
echo "Waiting for DB..."
python - <<'PY'
import os, time, psycopg
for i in range(60):
    try:
        psycopg.connect(
            host=os.getenv("POSTGRES_HOST","db"),
            port=os.getenv("POSTGRES_PORT","5432"),
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            connect_timeout=3,
        ).close()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("DB not reachable")
PY

echo "Apply migrations"
python manage.py migrate --noinput

echo "Collect static"
python manage.py collectstatic --noinput

# --- SEED opzionale e idempotente ---
SEED_FLAG="${SEED_ON_START:-0}"
SEED_MARK="/app/data/seed.hash"

if [ "$SEED_FLAG" = "1" ]; then
  mkdir -p /app/data
  if [ ! -f "$SEED_MARK" ]; then
    echo "Seeding from CSV (prima volta)..."
    set +e
    python manage.py seed_from_csv
    code=$?
    set -e
    if [ $code -eq 0 ]; then
      date +"%Y-%m-%d %H:%M:%S %Z" > "$SEED_MARK"
      echo "Seed OK, creato $SEED_MARK"
    else
      echo "Seed FALLITO (exit $code), avvio comunque l'app"
    fi
  else
    echo "Seed già eseguito (trovato $SEED_MARK), salto."
  fi
fi

if [ "$MODE" = "devserver" ]; then
  echo "Starting Django runserver (dev auto-reload)"
  exec python manage.py runserver 0.0.0.0:8000
else
  echo "Starting Gunicorn (non-root)"
  exec gunicorn progetto_lingua_2.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
fi
