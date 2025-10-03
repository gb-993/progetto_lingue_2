# docker/web/Dockerfile

# ---- Base comune (runtime minimale) ----
    FROM python:3.12-slim-bookworm AS base

    ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        PIP_NO_CACHE_DIR=1 \
        TZ=Europe/Rome
    
    # Strumenti minimi: curl per healthcheck (gosu rimosso perché non usato)
    RUN apt-get update && apt-get install -y --no-install-recommends \
          curl ca-certificates tzdata \
      && rm -rf /var/lib/apt/lists/*
    
    WORKDIR /app
    
    
    # ---- Stage deps (installa requirements con cache separata) ----
    FROM base AS deps
    
    COPY requirements.txt /app/requirements.txt
    
    # Se vuoi massima robustezza, NON forzare only-binary (alcune ruote mancano per py3.12)
    RUN python -m pip install --upgrade pip && \
        pip install -r /app/requirements.txt && \
        pip install "psycopg[binary]~=3.2"
    
    
    # ---- Stage finale (runtime pulito) ----
    FROM base AS final
    
    # Porta site-packages e script Python dallo stage deps
    COPY --from=deps /usr/local /usr/local
    
    # Copia l'entrypoint e normalizza EOL/permessi PRIMA del resto
    COPY entrypoint.sh /app/entrypoint.sh
    RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod 755 /app/entrypoint.sh
    
    # Ora copia il resto del progetto (inclusa data/ per seed in prod)
    COPY . /app
    
    # Utente non-root coerente
    RUN groupadd -g 1000 appuser && useradd -m -u 1000 -g 1000 appuser \
     && mkdir -p /app/staticfiles /app/media \
     && chown -R appuser:appuser /app
    
    # Passa all'utente non-root
    USER appuser
    
    EXPOSE 8000
    
    # L'entrypoint fa: wait DB, migrate, collectstatic, seed condizionato, avvio server
    ENTRYPOINT ["/app/entrypoint.sh"]
    