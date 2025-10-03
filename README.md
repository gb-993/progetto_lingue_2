STRUTTURA

progetto_lingua/
├─ manage.py
├─ venv/
├─ progetto_lingua_2/                 # progetto Django (settings/urls/asgi/wsgi)
│  ├─ __init__.py
│  ├─ asgi.py
│  ├─ settings.py                     # (oppure settings/… se l’hai splittato)
│  ├─ urls.py
│  └─ wsgi.py
├─ data/                              # dati/semi di test (CSV, ecc.)
│  └─ README.md                       # (opzionale: note su come ricaricare i dati)
├─ core/                              # modelli principali + logiche condivise
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ models.py                       # User, Language, ParameterDef, Question, Answer, …
│  ├─ views.py
│  ├─ services/
│  │  ├─ logic_parser.py
│  │  ├─ param_consolidate.py
│  │  └─ dag_eval.py
│  ├─ management/
│  │  └─ commands/
│  │     ├─ seed_from_csv.py
│  │     └─ rebuild_param_cache.py
│  └─ migrations/                     # (ignorare)
│     └─ 0001_initial.py
├─ accounts/                          # gestione utenti/admin, assegnazioni lingue
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
├─ languages_ui/                      # pagine lingua + valutazione DAG + debug
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ models.py                       # (se usato per helper/minimodel)
│  ├─ tests.py
│  ├─ urls.py
│  ├─ views.py                        # language_list, language_data, debug DAG, …
│  └─ migrations/
├─ parameters_ui/                     # CRUD ParameterDef + Question formset
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ forms.py                        # ParameterForm, QuestionFormSet (ModelForm/FBV)
│  ├─ urls.py
│  └─ views.py                        # FBV come preferito
├─ glossary_ui/                       # glossario (CRUD + ricerca)
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ models.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
├─ submissions_ui/                    # invii/compilazioni (liste, stato, ecc.)
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
├─ tablea_ui/                         # vista tabellare + export xlsx/csv
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ urls.py
│  └─ views.py                        # tablea_export_xlsx/csv, tabella lingue×param
├─ static/
│  ├─ css/
│  │  ├─ style.css
│  │  └─ mobile.css
│  └─ js/
│     ├─ add_question_form.js
│     └─ show_motivation.js
├─ templates/                         # template condivisi centralizzati
│  ├─ base.html
│  ├─ index.html
│  ├─ _partials/
│  │  └─ messages.html
│  ├─ accounts/
│  │  ├─ add.html
│  │  ├─ dashboard.html
│  │  ├─ edit.html
│  │  ├─ list.html
│  │  └─ login.html
│  ├─ glossary/
│  │  ├─ add.html
│  │  ├─ confirm_delete.html
│  │  ├─ edit.html
│  │  ├─ list.html
│  │  └─ view.html
│  ├─ languages/
│  │  ├─ add.html
│  │  ├─ data.html
│  │  ├─ debug_parameters.html
│  │  ├─ edit.html
│  │  └─ list.html
│  ├─ parameters/
│  │  ├─ edit.html
│  │  └─ list.html
│  └─ submissions/
│     └─ list.html
└─ locale/
   └─ it/
      └─ LC_MESSAGES/
         ├─ django.po
         └─ django.mo


PER AVVIARE 
python manage.py runserver

SE MODIFICHI DB
python manage.py makemigrations
python manage.py migrate
python manage.py runserver

