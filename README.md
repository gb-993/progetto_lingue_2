# PCM HUB - Ricerca linguistica

Piattaforma web per la raccolta, gestione e analisi di dati linguistici, con workflow editoriale (submission/review), export scientifici e deployment containerizzato.

# Documentazione
https://gb-993.github.io/progetto_lingue_2/

## Getting Started

Il progetto è configurato per usare **PostgreSQL** tramite variabili `POSTGRES_*` in `progetto_lingua_2/settings.py`.

### Opzione A (consigliata): avvio con Docker Compose

Prerequisiti:
- Docker + Docker Compose
- File `.env` configurato con almeno `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

Comandi:

```powershell
docker compose up --build
```

Note utili:
- Le migrazioni vengono eseguite automaticamente all'avvio del container `web` (`entrypoint.sh`).
- Lo script esegue anche seed iniziale (solo su DB vuoto), import glossario e `collectstatic`.
- L'app Django e servita da Gunicorn dietro Nginx (`compose.yml`, `docker/nginx/default.conf`).

### Opzione B: avvio locale (senza Docker)

Prerequisiti:
- Python 3.11+ (allineato al container `python:3.11-slim`)
- PostgreSQL raggiungibile e variabili ambiente `POSTGRES_*` valorizzate

1) Crea e attiva il virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

2) Installa le dipendenze

```powershell
pip install -r requirements.txt
```

3) Applica le migrazioni (necessarie al primo avvio e dopo ogni cambio schema)

```powershell
python manage.py migrate
```

4) (Opzionale ma consigliato) Carica dati iniziali

```powershell
python manage.py seed_from_csv
python manage.py seed_question_motivations
python manage.py import_glossary
```

5) Avvia il server di sviluppo

```powershell
python manage.py runserver
```

## Tech Stack

- **Python 3.11**  
  Linguaggio principale: garantisce ecosistema maturo per calcolo scientifico, manipolazione dati e integrazione con Django.

- **Django 5.x**  
  Framework backend per autenticazione, ORM, admin, template server-side e gestione robusta del dominio applicativo linguistico.

- **PostgreSQL 16**  
  Database relazionale di produzione (`django.db.backends.postgresql`), scelto per affidabilita, integrita dei dati e ottimo supporto a query complesse.

- **Gunicorn**  
  Application server WSGI per eseguire Django in ambiente production-like, con worker multipli e timeout configurabile.

- **Nginx**  
  Reverse proxy davanti a Gunicorn: gestisce routing HTTP e serve direttamente static/media per ridurre carico applicativo.

- **Docker & Docker Compose**  
  Orchestrazione dei servizi `web`, `db`, `nginx` (piu manutenzione periodica), utile per ambienti riproducibili e deploy coerenti.

- **WhiteNoise**  
  Gestione e compressione degli asset statici (`CompressedManifestStaticFilesStorage`) con caching aggressivo per performance migliori.

- **psycopg2-binary**  
  Driver PostgreSQL per Python/Django, necessario per la connessione ORM al database.

- **pyparsing**  
  Parsing delle espressioni logiche delle condizioni implicazionali (usato in `core/services/logic_parser.py`), utile per regole formali leggibili e validabili.

- **NumPy, SciPy, Matplotlib, adjustText**  
  Stack numerico/statistico per calcoli e visualizzazioni (es. analisi distanze, PCA, grafici esportabili).

- **openpyxl**  
  Import/export Excel, fondamentale per workflow di caricamento e condivisione dati linguistici.

- **fpdf2**  
  Generazione report PDF direttamente dall'applicazione.

## Note di coerenza documentale

- Questa versione del README e allineata ai file `progetto_lingua_2/settings.py`, `compose.yml`, `entrypoint.sh` e ai Dockerfile in `docker/`.
- In `compose.yml` e esposta anche la porta `443`, ma il file `docker/nginx/default.conf` attuale configura solo `listen 80`; se abiliti TLS, aggiungi configurazione SSL dedicata.
