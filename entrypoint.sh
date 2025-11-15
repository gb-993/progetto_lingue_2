#!/usr/bin/env bash
set -euo pipefail

# Wait for the PostgreSQL service to accept connections
until python - <<'PYCODE'
import os
import socket
host = os.environ.get('POSTGRES_HOST', 'db')
port = int(os.environ.get('POSTGRES_PORT', '5432'))
with socket.socket() as s:
    try:
        s.settimeout(1.0)
        s.connect((host, port))
    except Exception:
        raise SystemExit(1)
PYCODE
do
  echo "Waiting for database..."
  sleep 1
done

# Apply database migrations
python manage.py migrate --noinput

# SEED INIZIALE — esegui solo se non esistono ancora utenti o risposte
if ! python - <<'PY'
import django
django.setup()
from core.models import User, Answer
import sys
# restituisce 0 (exit code 0) se il DB ha già dati => seed non eseguito
sys.exit(0 if (User.objects.exists() or Answer.objects.exists()) else 1)
PY
then
    # esegui seed_from_csv per importare utenti, parametri, lingue, ecc.
    python manage.py seed_from_csv
    python manage.py import_language_from_excel --file data/Database_Chioggia.xlsx --language-name "Chioggia"

fi


# Collect static assets into /app/staticfiles
python manage.py collectstatic --noinput

# Start the Gunicorn application server
exec gunicorn progetto_lingua_2.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60