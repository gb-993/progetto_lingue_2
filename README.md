COMANDI RAPIDI

# Avvio
python manage.py runserver  

# Se modifichi il DB
python manage.py makemigrations  
python manage.py migrate  
python manage.py runserver  

```text
progetto_lingua/
├─ manage.py
│    → Il “pulsante di avvio” del progetto: serve a partire, fare aggiornamenti, ecc.
│
├─ venv/
│    → Lo spazio privato dove vive Python per questo progetto (non serve toccarlo).
│
├─ progetto_lingua_2/
│    → La cabina di regia: contiene le impostazioni generali del sito.
│    ├─ settings.py   → qui sono scritte le impostazioni (es. database, lingua, applicazioni attive).
│    ├─ urls.py       → la mappa che dice quali pagine esistono e dove puntano.
│    ├─ wsgi.py       → serve solo quando il sito è pubblicato online (modalità classica).
│    ├─ asgi.py       → come sopra, ma per modalità “moderna/veloce”.
│    └─ __init__.py   → file tecnico, indica a Python che questa è una cartella di codice.
│
├─ data/
│    → Cartella con dati di esempio o di test.
│
├─ core/
│    → La parte fondamentale: contiene la descrizione dei dati e le regole principali.
│    ├─ models.py     → descrive gli “oggetti” principali (utenti, lingue, parametri, risposte…).
│    ├─ admin.py      → permette di gestire questi dati dall’area di amministrazione.
│    ├─ views.py      → eventuali pagine comuni.
│    ├─ services/     → logiche più complicate (es. come valutare le risposte).
│    │    ├─ logic_parser.py       → interpreta le condizioni scritte sui parametri.
│    │    ├─ param_consolidate.py  → unisce e consolida le risposte date dagli utenti.
│    │    └─ dag_eval.py           → calcola i valori dei parametri usando un grafo (DAG).
│    ├─ management/commands/
│    │    ├─ seed_from_csv.py      → comando per caricare dati di esempio da file CSV.
│    │    └─ rebuild_param_cache.py→ comando per rigenerare la cache dei parametri.
│    └─ migrations/                → traccia gli aggiornamenti del database.
│
├─ accounts/
│    → Tutto ciò che riguarda gli utenti.
│    ├─ forms.py     → i moduli per login/registrazione/modifica utente.
│    ├─ views.py     → le pagine per gestire gli utenti.
│    ├─ urls.py      → l’elenco degli indirizzi relativi agli utenti.
│    ├─ admin.py     → gestione utenti lato amministrazione.
│    └─ apps.py      → file tecnico che dice a Django che questa è un’app.
│
├─ languages_ui/
│    → Pagine che riguardano le lingue.
│    ├─ forms.py     → moduli per modificare i dati di una lingua.
│    ├─ views.py     → pagine: elenco lingue, dettagli lingua, debug dei parametri.
│    ├─ urls.py      → indirizzi relativi alle lingue.
│    ├─ models.py    → eventuali oggetti specifici di supporto per la UI.
│    └─ tests.py     → controlli automatici (test).
│
├─ parameters_ui/
│    → Pagine dedicate ai parametri e alle domande collegate.
│    ├─ forms.py     → moduli per creare/modificare parametri e domande.
│    ├─ views.py     → pagine di creazione, modifica, elenco parametri.
│    ├─ urls.py      → indirizzi relativi ai parametri.
│    └─ apps.py      → configurazione tecnica.
│
├─ glossary_ui/
│    → Glossario dei termini linguistici.
│    ├─ models.py    → descrizione di come sono salvati i termini di glossario.
│    ├─ forms.py     → moduli per aggiungere/modificare termini.
│    ├─ views.py     → pagine per mostrare e modificare i termini.
│    ├─ urls.py      → indirizzi relativi al glossario.
│    └─ apps.py
│
├─ submissions_ui/
│    → Gestione degli invii/compilazioni delle lingue da parte degli utenti.
│    ├─ forms.py
│    ├─ views.py     → pagine elenco invii, stato invio, ecc.
│    ├─ urls.py
│    └─ apps.py
│
├─ tablea_ui/
│    → La grande tabella comparativa (Table A) e l’esportazione in Excel/CSV.
│    ├─ views.py     → pagina con tabella e pulsanti “Esporta”.
│    ├─ urls.py
│    └─ apps.py
│
├─ static/
│    → File fissi che servono al sito (grafica e funzioni).
│    ├─ css/         → i fogli di stile: colori, font, spaziature.
│    │    ├─ style.css
│    │    └─ mobile.css
│    └─ js/          → gli script che rendono le pagine interattive.
│         ├─ add_question_form.js
│         └─ show_motivation.js
│
├─ templates/
│    → I “modelli” delle pagine HTML (come scheletri da riempire).
│    ├─ base.html      → la struttura base comune (menu, intestazione, stile).
│    ├─ index.html     → la home page del sito.
│    ├─ _partials/
│    │    └─ messages.html   → blocco riutilizzabile per mostrare messaggi all’utente.
│    ├─ accounts/      → pagine legate agli utenti:
│    │    ├─ add.html
│    │    ├─ dashboard.html
│    │    ├─ edit.html
│    │    ├─ list.html
│    │    └─ login.html
│    ├─ glossary/      → pagine per il glossario:
│    │    ├─ add.html
│    │    ├─ confirm_delete.html
│    │    ├─ edit.html
│    │    ├─ list.html
│    │    └─ view.html
│    ├─ languages/     → pagine relative alle lingue:
│    │    ├─ add.html
│    │    ├─ data.html
│    │    ├─ debug_parameters.html
│    │    ├─ edit.html
│    │    └─ list.html
│    ├─ parameters/    → pagine per i parametri:
│    │    ├─ edit.html
│    │    └─ list.html
│    └─ submissions/   → pagine relative agli invii:
│         └─ list.html
│
└─ locale/
     → Traduzioni del sito in altre lingue (qui: italiano).
     └─ it/LC_MESSAGES/
          ├─ django.po   → file di testo con le frasi tradotte.
          └─ django.mo   → versione compilata usata dal sito.

```
