from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import Language, LanguageParameter, ParameterDef  # importa i modelli reali che usi

# tablea/views.py  — SOSTITUISCI tutta la funzione tablea_index con questa

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import Language, ParameterDef, LanguageParameterEval

@login_required
def tablea_index(request):
    # Intestazioni colonne e righe (ordinati per position)
    languages = list(
        Language.objects.order_by("position").only("id", "name_full", "position")
    )
    parameters = list(
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .only("id", "name", "implicational_condition", "position")
    )

    # Leggiamo i valori POST-DAG dalla tabella di eval
    # values() per essere leggeri e veloci
    eval_rows = LanguageParameterEval.objects.values(
        "language_parameter__language_id",
        "language_parameter__parameter_id",
        "value_eval",
    )

    # Mappa (param_id, lang_id) -> value_eval ('+','-','0')
    px = {
        (row["language_parameter__parameter_id"], row["language_parameter__language_id"]): row["value_eval"]
        for row in eval_rows
    }

    # Costruzione struttura per il template
    rows = []
    for p in parameters:
        cells = []
        for lang in languages:
            cells.append(px.get((p.id, lang.id), ""))  # "" se non valutato
        rows.append({
            "p": p,
            "cells": cells,
        })

    ctx = {
        "languages": languages,
        "parameters": parameters,  # opzionale
        "rows": rows,
    }
    return render(request, "tablea/index.html", ctx)

@login_required
def tablea_export_xlsx(request):
    return tablea_index(request)  # placeholder

@login_required
def tablea_export_csv(request):
    return tablea_index(request)  # placeholder


@login_required
def tablea_export_xlsx(request):
    return tablea_index(request)  # placeholder

@login_required
def tablea_export_csv(request):
    return tablea_index(request)  # placeholder
