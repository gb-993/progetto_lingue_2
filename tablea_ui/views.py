from __future__ import annotations
from io import BytesIO
import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

# NUOVO: importiamo anche Question e Answer per la seconda TableA (per questions)
from core.models import Language, ParameterDef, LanguageParameterEval, Question, Answer


def _build_tablea_matrix():
    """
    Costruisce intestazioni e valori della Table A basata sui PARAMETRI (COMPLETI, senza filtri).
    Ritorna:
      - headers: lista ["Label", "Name", "Implication", <lang ids...>]
      - rows: lista di righe, ognuna lista [label, name, implication, val1, val2, ...]
      - languages, parameters: lista di oggetti Language / ParameterDef usati per l'ordine colonne/righe.
    """
    # Stesso ordine lingue/parametri della versione originale
    languages = list(
        Language.objects.order_by("position").only(
            "id", "name_full", "position", "top_level_family", "historical_language"
        )
    )
    parameters = list(
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .only("id", "name", "implicational_condition", "position")
    )

    # Valori valutati (+/-/0) per ciascuna coppia parametro-lingua
    eval_rows = LanguageParameterEval.objects.values(
        "language_parameter__language_id",
        "language_parameter__parameter_id",
        "value_eval",
    )
    px = {
        (row["language_parameter__parameter_id"], row["language_parameter__language_id"]): row["value_eval"]
        for row in eval_rows
    }

    headers = ["Label", "Name", "Implication"] + [lang.id for lang in languages]

    export_rows = []
    for p in parameters:
        cells = [px.get((p.id, lang.id), "") for lang in languages]
        export_rows.append([p.id, p.name, p.implicational_condition or ""] + cells)

    return headers, export_rows, languages, parameters


def _build_tablea_questions_matrix():
    """
    Costruisce intestazioni e valori della seconda Table A basata sulle QUESTION:
    - una question per riga
    - per ogni lingua: valore "YES"/"NO" se esiste una Answer, altrimenti vuoto.
    Struttura identica a _build_tablea_matrix per poter riusare template e export:
      - headers: ["Label", "Name", "Implication", <lang ids...>]
        * Label        -> question.id
        * Name         -> question.text
        * Implication  -> parameter_id (del parametro a cui appartiene la question)
    """
    languages = list(
        Language.objects.order_by("position").only(
            "id", "name_full", "position", "top_level_family", "historical_language"
        )
    )

    # Ordiniamo le question per parametro.position e poi per id, così l'output è stabile.
    questions = list(
        Question.objects.filter(parameter__is_active=True)
        .select_related("parameter")
        .order_by("parameter__position", "id")
        .only("id", "text", "parameter")
    )

    # Recuperiamo tutte le Answer yes/no per le question attive
    ans_rows = Answer.objects.filter(question__in=questions).values(
        "language_id", "question_id", "response_text"
    )
    # Mappa (question_id, language_id) -> "YES"/"NO"
    ax = {}
    for row in ans_rows:
        val = (row["response_text"] or "").lower()
        if val == "yes":
            v = "YES"
        elif val == "no":
            v = "NO"
        else:
            v = ""
        ax[(row["question_id"], row["language_id"])] = v

    headers = ["Label", "Name", "Implication"] + [lang.id for lang in languages]

    export_rows = []
    for q in questions:
        # Usiamo parameter_id nella colonna "Implication" per mantenere la stessa struttura del template
        param_label = q.parameter_id or ""
        cells = [ax.get((q.id, lang.id), "") for lang in languages]
        export_rows.append([q.id, q.text, param_label] + cells)

    # Per coerenza con _build_tablea_matrix, ritorniamo la lista Question come "parameters"
    # (verrà usata solo per gli header nei file di export, non nel template).
    return headers, export_rows, languages, questions


@login_required
def tablea_index(request):
    """
    Pagina Table A con switch tra:
    - view = 'params'    -> Table A per parametri (+/-/0)
    - view = 'questions' -> Table A per question (YES/NO)
    I filtri family / historical si applicano allo stesso modo in entrambe le viste.
    """
    view_mode = (request.GET.get("view") or "params").strip().lower()
    if view_mode not in {"params", "questions"}:
        view_mode = "params"

    if view_mode == "questions":
        headers, export_rows, languages_all, items = _build_tablea_questions_matrix()
    else:
        headers, export_rows, languages_all, items = _build_tablea_matrix()

    # Filtri già esistenti
    selected_family = request.GET.get("family", "").strip()
    selected_historical = request.GET.get("historical", "all").strip()

    families_qs = (
        Language.objects.values_list("top_level_family", flat=True)
        .distinct()
        .order_by("top_level_family")
    )
    families = [f for f in families_qs]

    def _match(lang: Language) -> bool:
        if selected_family and (lang.top_level_family or "") != selected_family:
            return False
        if selected_historical == "yes" and not lang.historical_language:
            return False
        if selected_historical == "no" and lang.historical_language:
            return False
        return True

    # Sottinsieme di lingue che soddisfa i filtri
    languages = [l for l in languages_all if _match(l)]

    # Mappiamo gli indici (nelle colonne) delle lingue mantenute
    idx_map = [i for i, l in enumerate(languages_all) if l in languages]

    # rows_for_template: struttura identica a prima, ma la "p" è generica:
    # - view=params    -> p.id/name/implicational_condition = parametro
    # - view=questions -> p.id/name/implicational_condition = question
    rows_for_template = []
    for r in export_rows:
        label, name, implication, *vals = r
        filtered_vals = [vals[i] for i in idx_map] if idx_map else []
        rows_for_template.append(
            {
                "p": type(
                    "P",
                    (),
                    {"id": label, "name": name, "implicational_condition": implication},
                )(),
                "cells": filtered_vals,
            }
        )

    ctx = {
        "languages": languages,
        # "items" può essere la lista di ParameterDef o di Question (usata solo per export/diagnostica se serve)
        "items": items,
        "rows": rows_for_template,
        "families": families,
        "selected_family": selected_family,
        "selected_historical": selected_historical,
        "view": view_mode,  # usato per lo switch nel template e per aggiungere ?view=...
    }
    return render(request, "tablea/index.html", ctx)


@login_required
def tablea_export_csv(request):
    """
    Export transposto:
    - se view=params    -> righe = lingue, colonne = parametri (+/-/0)
    - se view=questions -> righe = lingue, colonne = questions (YES/NO)
    """
    view_mode = (request.GET.get("view") or "params").strip().lower()
    if view_mode not in {"params", "questions"}:
        view_mode = "params"

    if view_mode == "questions":
        headers, export_rows, languages, items = _build_tablea_questions_matrix()
    else:
        headers, export_rows, languages, items = _build_tablea_matrix()

    # items = lista di colonne (ParameterDef oppure Question)
    transposed_header = ["Language"] + [getattr(p, "id", "") for p in items]

    transposed_rows = []
    for lang_index, lang in enumerate(languages):
        # Ogni riga di export_rows ha: [label, name, implication, val_lang0, val_lang1, ...]
        row_values_for_items = [
            export_rows[item_idx][3 + lang_index]  # indice 3 = dopo label/name/implication
            for item_idx in range(len(items))
        ]
        transposed_rows.append([lang.id] + row_values_for_items)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = "tableA_questions.csv" if view_mode == "questions" else "tableA.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # BOM per Excel

    writer = csv.writer(response, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(transposed_header)
    writer.writerows(transposed_rows)
    return response


@login_required
def tablea_export_xlsx(request):
    """
    Export Excel "non transposto":
    - righe = parametri o questions
    - colonne = Label, Name, Implication/Parameter, <lingue ...>
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    view_mode = (request.GET.get("view") or "params").strip().lower()
    if view_mode not in {"params", "questions"}:
        view_mode = "params"

    if view_mode == "questions":
        headers, export_rows, *_ = _build_tablea_questions_matrix()
    else:
        headers, export_rows, *_ = _build_tablea_matrix()

    wb = Workbook()
    ws = wb.active
    ws.title = "Table A"

    # Intestazioni
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Dati
    for row in export_rows:
        ws.append(row)

    # Fissa la prima riga
    ws.freeze_panes = "A2"

    # Larghezze colonne min/max base
    for col_idx, header in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(8, min(40, len(str(header)) + 2))

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = "tableA_questions.xlsx" if view_mode == "questions" else "tableA.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
