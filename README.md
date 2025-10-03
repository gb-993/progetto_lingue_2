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
├─ venv/
├─ progetto_lingua_2/
│  ├─ __init__.py
│  ├─ asgi.py
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py
│
├─ data/
│  └─ README.md
│
├─ core/
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ models.py
│  ├─ views.py
│  ├─ services/
│  │  ├─ logic_parser.py
│  │  ├─ param_consolidate.py
│  │  └─ dag_eval.py
│  ├─ management/
│  │  └─ commands/
│  │     ├─ seed_from_csv.py
│  │     └─ rebuild_param_cache.py
│  └─ migrations/
│     └─ 0001_initial.py
│
├─ accounts/
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
│
├─ languages_ui/
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ models.py
│  ├─ tests.py
│  ├─ urls.py
│  └─ views.py
│
├─ parameters_ui/
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
│
├─ glossary_ui/
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ models.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
│
├─ submissions_ui/
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ forms.py
│  ├─ urls.py
│  └─ views.py
│
├─ tablea_ui/
│  ├─ __init__.py
│  ├─ apps.py
│  ├─ urls.py
│  └─ views.py
│
├─ static/
│  ├─ css/
│  │  ├─ style.css
│  │  └─ mobile.css
│  └─ js/
│     ├─ add_question_form.js
│     └─ show_motivation.js
│
├─ templates/
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
│
└─ locale/
   └─ it/
      └─ LC_MESSAGES/
         ├─ django.po
         └─ django.mo
```
