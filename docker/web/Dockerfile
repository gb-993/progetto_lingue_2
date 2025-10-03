# --- Base immagine: Debian bookworm slim, fissata a minor per stabilità
FROM python:3.12.6-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Rome

# Dipendenze runtime minime + gosu per drop-privileges
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl ca-certificates locales gosu \
 && sed -i '/it_IT.UTF-8/s/^# //g' /etc/locale.gen && locale-gen \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Stage deps: installa requirements con cache separata
FROM base AS deps
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && python -m pip install --only-binary=:all: -r /app/requirements.txt

# --- Final: runtime pulito
FROM base AS final

# Porta con sé l'ambiente Python (site-packages, scripts)
COPY --from=deps /usr/local /usr/local

# Copia il progetto
COPY . /app

# 🔧 FIX Windows: converti CRLF -> LF e rendi eseguibile l'entrypoint
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Crea utente non-root con UID/GID stabili (1000:1000)
RUN groupadd -g 1000 appuser && useradd -m -u 1000 -g 1000 appuser

# Pre-crea le directory (nel layer immagine — NON nei volumi)
RUN mkdir -p /app/staticfiles /app/media

EXPOSE 8000

# Lasciamo l'entrypoint partire come root: farà fix permessi e poi droppa
ENTRYPOINT ["/app/entrypoint.sh"]
