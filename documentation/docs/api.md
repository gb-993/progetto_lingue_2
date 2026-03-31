# API e routing completo del sito PCM-Hub

## 1) Panoramica

Questa pagina documenta tutte le route esposte dal progetto Django `progetto_lingua_2`, incluse:

- pagine HTML (UI server-rendered)
- endpoint JSON
- endpoint di export (XLSX, CSV, ZIP, PNG, PDF)
- route operative/tecniche (`health`, `admin`, `test500`)

Base URL (esempi):

- locale: `http://127.0.0.1:8000`
- container/reverse-proxy: dipende da `DJANGO_ALLOWED_HOSTS` e dal deployment

## 2) Autenticazione, ruoli e policy accesso

### Autenticazione

- Autenticazione Django standard (`/accounts/login/`, `/accounts/logout/`)
- `LOGIN_URL = /accounts/login/`
- Molte route richiedono sessione autenticata (`@login_required`)

### Ruoli applicativi rilevati

- `admin`: gestione completa (utenti, parametri, approvazioni, backup, import/export globali)
- `user`: compilazione dati su lingue assegnate
- `public`: dashboard pubblica autenticata
- `linguist`: abilitato almeno alla sezione `queries` (check specifico)

### Middleware Terms Acceptance

Middleware attivo: `accounts.middleware.TermsAcceptanceMiddleware`.

Comportamento:

- se utente autenticato non ha accettato i termini -> redirect a `/accounts/accept-terms/`
- eccezioni consentite: route `accept_terms`, `logout`, path statici
- se i PDF termini/informativa cambiano (mtime piu recente), l'accettazione precedente viene invalidata

### Convenzioni metodi HTTP

- Dove non presente `@require_POST`/`@require_http_methods`, il metodo e gestito internamente (spesso GET+POST)
- Endpoint JSON in genere rispondono con `JsonResponse`
- Endpoint export rispondono con `Content-Disposition: attachment`

## 3) Route root e sistema

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/` | `RedirectView(pattern_name='dashboard')` | no | redirect | Redirect alla dashboard |
| * | `/admin/` | Django Admin | staff/admin | HTML | Backoffice Django |
| GET | `/health/` | `core.views_health.health` | no | text/plain | Ritorna `ok` |
| GET | `/test500/` | `core.views.test_500` | no | errore 500 | Endpoint di test errore |
| GET/POST | `/accounts/password-reset/` | `PasswordResetView` | no | HTML | Avvio reset password |
| GET | `/accounts/password-reset/done/` | `PasswordResetDoneView` | no | HTML | Conferma invio reset |
| GET/POST | `/accounts/reset/<uidb64>/<token>/` | `PasswordResetConfirmView` | no | HTML | Nuova password |
| GET | `/accounts/reset/done/` | `PasswordResetCompleteView` | no | HTML | Reset completato |

Include root:

- `/accounts/` -> `accounts.urls`
- `/languages/` -> `languages_ui.urls`
- `/parameters/` -> `parameters_ui.urls`
- `/glossary/` -> `glossary_ui.urls`
- `/graphs/` -> `graphs_ui.urls`
- `/table-a/` -> `tablea_ui.urls`
- `/submissions/` -> `submissions_ui.urls`
- `/queries/` -> `queries.urls`
- `/instruction/` -> `instruction_ui.urls`
- `/questions/` -> `questions_ui.urls`

In `DEBUG=True` sono servite anche route static/media via Django (`/static/`, `/media/`).

## 4) Modulo Accounts (`/accounts/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/accounts/dashboard/` | `dashboard` | login | HTML | Dashboard per ruolo |
| GET | `/accounts/about/` | `TemplateView` | no | HTML | Pagina pubblica |
| GET | `/accounts/team/` | `TemplateView` | no | HTML | Pagina pubblica |
| GET | `/accounts/methodology/` | `TemplateView` | no | HTML | Pagina pubblica |
| GET | `/accounts/contacts/` | `TemplateView` | no | HTML | Pagina pubblica |
| GET/POST | `/accounts/accept-terms/` | `accept_terms` | login | HTML/redirect | Accettazione termini |
| GET | `/accounts/` | `accounts_list` | admin | HTML | Lista account |
| GET/POST | `/accounts/add/` | `accounts_add` | admin | HTML/redirect | Crea account |
| GET/POST | `/accounts/<int:user_id>/edit/` | `accounts_edit` | admin | HTML/redirect | Modifica account |
| GET/POST | `/accounts/login/` | `LoginView` | no | HTML | Login con `EmailAuthForm` |
| GET/POST | `/accounts/logout/` | `LogoutView` | login | redirect | Logout verso `/accounts/login/` |
| GET/POST | `/accounts/me/` | `my_account` | login | HTML/redirect | Profilo/password utente |
| GET/POST | `/accounts/<int:user_id>/delete/` | `accounts_delete` | admin | HTML/redirect | Conferma+delete account |
| GET | `/accounts/how-to-cite/` | `how_to_cite` | no | HTML | Pagina citazione con contenuti DB |
| GET/POST | `/accounts/edit-content/<str:key>/` | `edit_site_content` | admin | HTML/redirect | Modifica contenuti pagina citazione |

## 5) Modulo Languages (`/languages/`)

### CRUD e navigazione lingua

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/languages/` | `language_list` | login | HTML | Lista lingue con filtri/sort |
| GET/POST | `/languages/add/` | `language_add` | login | HTML/redirect | Creazione lingua |
| GET/POST | `/languages/<str:lang_id>/edit/` | `language_edit` | login | HTML/redirect | Modifica lingua |
| POST | `/languages/<str:lang_id>/delete/` | `language_delete` | login + admin check | redirect | Richiede password admin |
| GET | `/languages/<str:lang_id>/` | `language_data` | login + access policy | HTML | Pagina compilazione parametri/domande |

### Salvataggio, workflow review e debug

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| POST | `/languages/<str:lang_id>/parameters/<str:param_id>/save/` | `parameter_save` | login + access policy | redirect | Salva tutte le risposte del parametro |
| POST | `/languages/<str:lang_id>/answers/<str:question_id>/save/` | `answer_save` | login + access policy | redirect | Salva singola risposta |
| POST | `/languages/<str:lang_id>/submit/` | `language_submit` | login + access policy | redirect | Invia per approvazione |
| POST | `/languages/<str:lang_id>/approve/` | `language_approve` | admin | redirect | Approva + esegue DAG |
| POST | `/languages/<str:lang_id>/reject/` | `language_reject` | admin | redirect | Rigetta submission |
| POST | `/languages/<str:lang_id>/reopen/` | `language_reopen` | login + access policy | redirect | Riapre risposte rejected |
| GET | `/languages/<str:lang_id>/debug/` | `language_debug` | admin + access policy | HTML | Diagnostica parametri/condizioni |
| POST | `/languages/<str:lang_id>/run_dag/` | `language_run_dag` | admin | redirect | Forza approvazione + DAG |

### Review flags (JSON)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/languages/<str:lang_id>/review-flags/` | `review_flags_list` | login + access policy | JSON | Lista parametri flaggati utente |
| POST | `/languages/<str:lang_id>/review-flags/<str:param_id>/toggle/` | `toggle_review_flag` | login + access policy | JSON | Set/unset flag parametro |

### Import/export

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET/POST | `/languages/import-excel/` | `language_import_excel` | admin | HTML/redirect | Import lingue da file Excel |
| GET | `/languages/export.xlsx` | `language_list_export_xlsx` | login | XLSX | Export lista lingue filtrata |
| GET | `/languages/<str:lang_id>/export/` | `language_export_xlsx` | login + access policy | XLSX | Export singola lingua |
| GET | `/languages/export-all.zip` | `language_export_all_zip` | admin | ZIP | Export XLSX di tutte le lingue |

## 6) Modulo Parameters (`/parameters/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/parameters/` | `parameter_list` | admin | HTML | Lista parametri |
| GET/POST | `/parameters/add/` | `parameter_add` | admin | HTML/redirect | Creazione parametro |
| GET/POST | `/parameters/<str:param_id>/edit/` | `parameter_edit` | admin | HTML/redirect | Modifica parametro + changelog |
| POST | `/parameters/<str:param_id>/deactivate/` | `parameter_deactivate` | admin | redirect/HTML400 | Disattivazione sicura |
| GET/POST | `/parameters/parameters/<str:param_id>/questions/add/` | `question_add` | admin | HTML/redirect | Aggiunta domanda |
| GET/POST | `/parameters/parameters/<str:param_id>/questions/<str:question_id>/edit/` | `question_edit` | admin | HTML/redirect | Modifica domanda |
| GET/POST | `/parameters/parameters/<str:param_id>/questions/<str:question_id>/delete/` | `question_delete` | admin | HTML/redirect | Conferma+cancellazione domanda |
| GET/POST | `/parameters/<str:param_id>/questions/import/` | `question_clone` | admin | HTML/redirect | Clonazione domanda |
| GET/POST | `/parameters/lookups/` | `lookups_manage` | admin | HTML/partial/redirect | Gestione lookup schema/tipo/livello |
| GET/POST | `/parameters/parameters/motivations/` | `motivations_manage` | admin | HTML/redirect | Gestione motivazioni |
| GET/POST | `/parameters/parameters/motivations/<int:mot_id>/edit/` | `motivation_edit` | admin | HTML/redirect | Modifica motivazione |
| GET | `/parameters/parameters/<str:param_id>/pdf/` | `parameter_download_pdf` | admin | PDF | Report parametro |
| GET | `/parameters/languages/<str:lang_id>/review-flags/` | `review_flags_list` | login | JSON | Lista flag review utente |
| POST | `/parameters/languages/<str:lang_id>/parameters/<str:param_id>/review-flag/` | `toggle_review_flag` | login | JSON/400 | Toggle flag review |

## 7) Modulo Glossary (`/glossary/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/glossary/` | `glossary_list` | login | HTML | Lista con ricerca/paginazione |
| GET/POST | `/glossary/add/` | `glossary_add` | admin | HTML/redirect | Nuova voce |
| GET | `/glossary/<str:word>/` | `glossary_view` | login | HTML | Dettaglio voce |
| GET/POST | `/glossary/<str:word>/edit/` | `glossary_edit` | admin | HTML/redirect | Modifica voce |
| GET/POST | `/glossary/<str:word>/delete/` | `glossary_delete` | admin | HTML/redirect | Conferma+cancellazione |

## 8) Modulo Graphs (`/graphs/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/graphs/parameters/` | `parameters_graph` | login | HTML | Pagina grafico parametri |
| GET | `/graphs/api/graph.json` | `api_graph` | login | JSON | Nodi+archi da implicational conditions |
| GET | `/graphs/api/lang-values.json?lang=<id>` | `api_lang_values` | login | JSON | Valori finali parametri per lingua |

### Esempio risposta `api_graph`

```json
{
  "nodes": [{"data": {"id": "P1", "label": "P1"}}],
  "edges": [{"data": {"id": "P0->P1", "source": "P0", "target": "P1"}}]
}
```

### Esempio risposta `api_lang_values`

```json
{
  "language": {"id": "it", "name": "Italian"},
  "values": [
    {"id": "P1", "label": "P1 - Example", "final": "+", "active": true}
  ]
}
```

## 9) Modulo Table A (`/table-a/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/table-a/` | `tablea_index` | login | HTML/partial | Supporta HTMX (`HX-Request`) |
| GET | `/table-a/export.xlsx` | `tablea_export_xlsx` | login | XLSX | Export matrice corrente |
| GET | `/table-a/export_questions.xlsx` | `tablea_export_questions_xlsx` | login | XLSX | Export orientato alle domande |
| GET | `/table-a/export.csv` | `tablea_export_csv` | login | CSV | Export trasposto per lingua |
| GET | `/table-a/distances.zip` | `tablea_export_distances_zip` | login | ZIP | Matrici Hamming/Jaccard |
| GET | `/table-a/dendrograms.zip` | `tablea_export_dendrogram` | login | ZIP | Dendrogrammi PNG |
| GET | `/table-a/pca.png` | `tablea_export_pca` | login | PNG | Scatterplot PCA |

Filtri principali via querystring:

- lingue: `f_lang_top_family`, `f_lang_family`, `f_lang_grp`, `f_lang_hist`, `f_lang_specific`
- vista: `view=params|questions`
- filtri parametro: `f_p_schema`, `f_p_type`, `f_p_level`
- filtri domanda: `f_q_template`, `f_q_stop`

## 10) Modulo Submissions (`/submissions/`)

Tutte le route del modulo sono riservate ad admin autenticati.

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/submissions/` | `submissions_list` | admin | HTML | Lista backup/cartelle |
| GET | `/submissions/<int:submission_id>/` | `submission_detail` | admin | HTML | Dettaglio snapshot |
| GET/POST | `/submissions/create/<str:language_id>/` | `submission_create_for_language` | admin | HTML/redirect | Crea backup singola lingua |
| GET/POST | `/submissions/create-all/` | `submission_create_all_languages` | admin | HTML/redirect | Crea backup globale sincronizzato |
| POST (consigliato) | `/submissions/delete-backup/` | `submission_delete_backup` | admin | redirect | Elimina backup per timestamp |

## 11) Modulo Queries (`/queries/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/queries/` | `home` | login + role check | HTML/partial | Accesso consentito a admin/staff/linguist |

Caratteristiche:

- multi-tab logiche (`q1`...`q9`) via query params
- rendering parziale con HTMX: template `queries/partials/results.html`
- analisi su implicazioni, neutralizzazioni, distribuzioni e confronti tra lingue

## 12) Modulo Instruction (`/instruction/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/instruction/instructions/` | `instruction` | login | HTML | Pagina istruzioni con contenuti dinamici |
| POST | `/instruction/api/update-content/` | `update_site_content` | login + admin check | JSON | Aggiorna/crea blocchi `SiteContent` |

Payload JSON atteso per update:

```json
{
  "key": "instr_example",
  "content": "Testo aggiornato",
  "page": "Instructions"
}
```

Risposte tipiche:

- `200`: `{"status": "success"}`
- `400`: `{"error": "Key is required"}`
- `403`: `{"error": "Unauthorized"}`

## 13) Modulo Questions (`/questions/`)

| Metodo | Path | View | Auth | Output | Note |
|---|---|---|---|---|---|
| GET | `/questions/all/` | `question_list` | admin | HTML | Lista globale domande con ricerca |

## 14) Errori, status code e sicurezza

Pattern osservati nel codice:

- `200`: render HTML/JSON standard
- `302`: redirect post-azione
- `400`: input non valido (`HttpResponseBadRequest`, validazioni)
- `403`: accesso non autorizzato (alcuni endpoint JSON)
- `404`: risorsa non trovata / access denied mascherato
- `500`: eccezioni non gestite (`/test500/` forza questo caso)

Sicurezza applicata:

- CSRF middleware attivo
- protezione clickjacking (`X_FRAME_OPTIONS = DENY`)
- WhiteNoise per static in deploy
- policy cookie `SameSite=Lax`

## 15) Note operative per manutenzione docs

Per mantenere questa pagina aggiornata, verificare a ogni release:

1. `progetto_lingua_2/urls.py`
2. tutti i file `*/urls.py`
3. decorator e metodi HTTP in `*/views.py`
4. eventuali nuove route JSON/export e relativi payload

