COMANDI RAPIDI

# Avvio
python manage.py runserver  

# Se modifichi il DB
python manage.py makemigrations  
python manage.py migrate  
python manage.py runserver  

```text
progetto_lingua/
├─ manage.py               # il “pulsante di avvio” del progetto
├─ venv/                   # la cartella dove vive Python per questo progetto
│
├─ progetto_lingua_2/      # il cuore del sito: configurazioni generali
│  ├─ settings.py          # le impostazioni (es. database, lingua, app attive)
│  ├─ urls.py              # la mappa delle pagine del sito
│  ├─ wsgi.py / asgi.py    # servono solo quando il sito va online
│
├─ data/                   # dati di esempio usati per testare
│
├─ core/                   # la “base dati” e le regole fondamentali
│  ├─ models.py            # descrizione delle tabelle principali (utenti, lingue, domande…)
│  ├─ services/            # logiche più complicate (es. calcoli sui parametri)
│  └─ management/commands/ # piccoli comandi per caricare o aggiornare i dati
│
├─ accounts/               # gestione degli utenti (registrazione, login, ruoli)
├─ languages_ui/           # pagine dedicate alle lingue
├─ parameters_ui/          # pagine dedicate ai parametri e alle domande
├─ glossary_ui/            # glossario dei termini linguistici
├─ submissions_ui/         # gestione degli invii/compilazioni fatti dagli utenti
├─ tablea_ui/              # la tabella comparativa finale e l’esportazione
│
├─ static/                 # grafica e funzioni lato utente
│  ├─ css/                 # i fogli di stile (aspetto del sito)
│  ├─ js/                  # gli script che rendono le pagine interattive
│  └─ img/                 # eventuali immagini
│
├─ templates/              # i “modelli” delle pagine del sito
│  ├─ base.html            # la struttura comune (menu, stile generale)
│  ├─ accounts/            # pagine utenti (login, lista, modifica…)
│  ├─ languages/           # pagine lingue
│  ├─ parameters/          # pagine parametri
│  ├─ glossary/            # pagine glossario
│  └─ submissions/         # pagine invii
│
└─ locale/                 # traduzioni (qui in italiano)

```
