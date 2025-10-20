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
    Costruisce intestazioni e valori della Table A (COMPLETI, senza filtri).
    Ritorna:
      - headers: lista ["Label", "Name", "Implication", <lang ids...>]
      - rows: lista di righe, ognuna lista [label, name, implication, val1, val2, ...]
      - languages, parameters: queryset valutati (per il template)
    """
    # Colonne (lingue) e righe (parametri)
    languages = list(
        Language.objects.order_by("position").only("id", "name_full", "position", "top_level_family", "historical_language")
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

    # Header pieno
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
    headers, export_rows, languages_all, parameters = _build_tablea_matrix()

    # --- Filtri SOLO per visualizzazione ---
    selected_family = request.GET.get("family", "").strip()
    selected_historical = request.GET.get("historical", "all").strip()  # 'all' | 'yes' | 'no'

    # Opzioni per select family (distinte, ordinate)
    families_qs = Language.objects.values_list("top_level_family", flat=True).distinct().order_by("top_level_family")
    families = [f for f in families_qs]

    # Filtra l'elenco delle lingue (colonne) da visualizzare
    def _match(lang):
        if selected_family and (lang.top_level_family or "") != selected_family:
            return False
        if selected_historical == "yes" and not lang.historical_language:
            return False
        if selected_historical == "no" and lang.historical_language:
            return False
        return True

    languages = [l for l in languages_all if _match(l)]

    # Prepara indici delle colonne scelte per filtrare anche i valori nelle righe
    # export_rows = [label, name, implication, <val0>, <val1>, ...] in ordine languages_all
    idx_map = [i for i, l in enumerate(languages_all) if l in languages]

    rows_for_template = []
    for r in export_rows:
        label, name, implication, *vals = r
        filtered_vals = [vals[i] for i in idx_map] if idx_map else []
        rows_for_template.append({
            "p": type("P", (), {"id": label, "name": name, "implicational_condition": implication})(),
            "cells": filtered_vals,
        })

    ctx = {
        "languages": languages,
        "parameters": parameters,
        "rows": rows_for_template,
        # per i filtri
        "families": families,
        "selected_family": selected_family,
        "selected_historical": selected_historical,
    }
    return render(request, "tablea/index.html", ctx)


@login_required
def tablea_export_csv(request):
    # Costruisci i dati COMPLETI (nessun filtro per export)
    headers, export_rows, *_ = _build_tablea_matrix()

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="tableA.csv"'
    response.write("\ufeff")  # BOM per Excel/Windows

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
        ws.column_dimensions[col_letter].width = max(8, min(40, len(str(header)) + 2))

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="tableA.xlsx"'
    return response
