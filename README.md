# PCM HUB - Ricerca linguistica

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.x-092E20?style=flat-square&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)

> Piattaforma web per la raccolta, gestione e analisi di dati linguistici, con workflow editoriale (submission/review), export scientifici e deployment containerizzato.

---

## Getting Started

Il progetto è configurato per usare **PostgreSQL** tramite le variabili `POSTGRES_*` configurabili nel file `progetto_lingua_2/settings.py`.

### Opzione A: Avvio con Docker Compose (Consigliata)

**Prerequisiti:**
- Docker + Docker Compose installati
- File `.env` configurato con almeno: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

```powershell
docker compose up --build
```

> **Note utili per Docker:**
> - Le migrazioni vengono eseguite automaticamente all'avvio del container `web` tramite `entrypoint.sh`.
> - Lo script esegue anche il seed iniziale (solo su DB vuoto), l'import del glossario e il `collectstatic`.
> - L'app Django è servita da **Gunicorn** dietro **Nginx** (configurato in `compose.yml` e `docker/nginx/default.conf`).

### Opzione B: Avvio Locale (Senza Docker)

**Prerequisiti:**
- Python 3.11+ (allineato al container `python:3.11-slim`)
- PostgreSQL raggiungibile e variabili ambiente `POSTGRES_*` valorizzate

**1. Crea e attiva il virtual environment**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**2. Installa le dipendenze**
```powershell
pip install -r requirements.txt
```

**3. Applica le migrazioni** *(necessarie al primo avvio e dopo ogni cambio di schema)*
```powershell
python manage.py migrate
```

**4. Carica i dati iniziali** *(Opzionale ma consigliato)*
```powershell
python manage.py seed_from_csv
python manage.py seed_question_motivations
python manage.py import_glossary
```

**5. Avvia il server di sviluppo**
```powershell
python manage.py runserver
```

---

## Tech Stack

### Core & Backend
- **[Python 3.11](https://www.python.org/):** Garantisce un ecosistema maturo per il calcolo scientifico e l'integrazione con Django.
- **[Django 5.x](https://www.djangoproject.com/):** Framework per autenticazione, ORM, admin e gestione robusta del dominio linguistico.
- **[PostgreSQL 16](https://www.postgresql.org/):** Database relazionale di produzione, scelto per affidabilità e supporto a query complesse (tramite `psycopg2-binary`).

### Infrastruttura & Deployment
- **[Docker & Docker Compose](https://www.docker.com/):** Orchestrazione dei servizi (`web`, `db`, `nginx`) per ambienti riproducibili.
- **[Gunicorn](https://gunicorn.org/) & [Nginx](https://nginx.org/):** Application server WSGI e reverse proxy per la gestione ottimizzata del traffico e degli asset.
- **[WhiteNoise](http://whitenoise.evans.io/):** Gestione, compressione e caching aggressivo degli asset statici.

### Data Science & Tooling Linguistico
- **Analisi e Calcolo:** `NumPy`, `SciPy`, `Matplotlib`, `adjustText` per stack numerico/statistico (analisi distanze, PCA, grafici esportabili).
- **Elaborazione Dati:** `pyparsing` per il parsing delle espressioni logiche, `openpyxl` per import/export Excel e `fpdf2` per la generazione di report PDF.

---

## Note di coerenza documentale

* Questa versione del README è allineata ai file `progetto_lingua_2/settings.py`, `compose.yml`, `entrypoint.sh` e ai Dockerfile in `docker/`.
* Nel file `compose.yml` è esposta anche la porta `443`, ma il file `docker/nginx/default.conf` attuale configura solo `listen 80`. **Se abiliti il TLS**, ricordati di aggiungere la configurazione SSL dedicata.
