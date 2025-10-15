# tablea/views.py — SOSTITUISCI INTERO FILE

from __future__ import annotations
from io import BytesIO
import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from core.models import Language, ParameterDef, LanguageParameterEval

# ---------- Utility condivisa ----------

def _build_tablea_matrix():
    """
    Costruisce intestazioni e valori della Table A.
    Ritorna:
      - headers: lista ["Label", "Name", "Implication", <lang ids...>]
      - rows: lista di righe, ognuna lista [label, name, implication, val1, val2, ...]
      - languages, parameters: queryset valutati (per il template)
    """
    # Colonne (lingue) e righe (parametri)
    languages = list(
        Language.objects.order_by("position").only("id", "name_full", "position")
    )
    parameters = list(
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .only("id", "name", "implicational_condition", "position")
    )

    # Mappa (param_id, lang_id) -> value_eval ('+','-','0') dalla tabella di eval
    eval_rows = LanguageParameterEval.objects.values(
        "language_parameter__language_id",
        "language_parameter__parameter_id",
        "value_eval",
    )
    px = {
        (row["language_parameter__parameter_id"], row["language_parameter__language_id"]): row["value_eval"]
        for row in eval_rows
    }

    # Header
    headers = ["Label", "Name", "Implication"] + [lang.id for lang in languages]

    # Righe per export (liste pure, utili sia per CSV che XLSX)
    export_rows = []
    for p in parameters:
        cells = [px.get((p.id, lang.id), "") for lang in languages]
        export_rows.append([p.id, p.name, p.implicational_condition or ""] + cells)

    return headers, export_rows, languages, parameters


# ---------- Views ----------

@login_required
def tablea_index(request):
    headers, export_rows, languages, parameters = _build_tablea_matrix()

    # Prepara struttura per il template (come avevi prima)
    rows_for_template = []
    # export_rows: [label, name, implication, val1, ...]
    for r in export_rows:
        label, name, implication, *vals = r
        rows_for_template.append({
            "p": type("P", (), {"id": label, "name": name, "implicational_condition": implication})(),
            "cells": vals,
        })

    ctx = {
        "languages": languages,
        "parameters": parameters,
        "rows": rows_for_template,
    }
    return render(request, "tablea/index.html", ctx)


@login_required
def tablea_export_csv(request):
    # Costruisci i dati
    headers, export_rows, *_ = _build_tablea_matrix()

    # Risposta CSV (UTF-8 BOM per compatibilità Excel su Windows)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="tableA.csv"'

    # Scrivi BOM
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    writer.writerows(export_rows)
    return response


@login_required
def tablea_export_xlsx(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    headers, export_rows, *_ = _build_tablea_matrix()

    wb = Workbook()
    ws = wb.active
    ws.title = "Table A"

    # Header
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Dati
    for row in export_rows:
        ws.append(row)

    # Freeze header
    ws.freeze_panes = "A2"

    # Larghezza colonne: un minimo per leggibilità
    for col_idx, header in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        # heuristica: max tra header e 8
        ws.column_dimensions[col_letter].width = max(8, min(40, len(str(header)) + 2))

    # Salva in memoria
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Risposta
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="tableA.xlsx"'
    return response
