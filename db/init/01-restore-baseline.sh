#!/usr/bin/env bash
set -euo pipefail
# Script eseguito automaticamente dall'immagine postgres QUANDO il volume è vuoto.
# Ripristina /docker-entrypoint-initdb.d/baseline.dump dentro $POSTGRES_DB.

echo "[initdb] Ripristino baseline in $POSTGRES_DB ..."
pg_restore \
  --clean --if-exists \
  --no-owner --no-privileges \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  "/docker-entrypoint-initdb.d/baseline.dump"

echo "[initdb] Baseline ripristinata."
