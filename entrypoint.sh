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

# Collect static assets into /app/staticfiles
python manage.py collectstatic --noinput

# Start the Gunicorn application server
exec gunicorn progetto_lingua_2.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60