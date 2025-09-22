from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import Language, LanguageParameter, ParameterDef  # importa i modelli reali che usi

@login_required
def tablea_index(request):
    # 1) Prendiamo intestazioni
    languages = list(Language.objects.order_by("position").only("id", "name_full"))
    parameters = list(ParameterDef.objects.filter(is_active=True).order_by("position").only("id", "name"))

    # 2) Qui costruisci la “px” (mappa param×lang -> valore).
    #    Per ora metto un esempio vuoto che restituisce stringhe vuote.
    #    Se hai già una fonte (es. LanguageParameterEval o altro), popola 'px' lì sotto.
    px = {}
    for lp in LanguageParameter.objects.select_related("language", "parameter"):
        px[(lp.parameter_id, lp.language_id)] = lp.value_orig
    # Esempio (se avessi dati): px[(param_id, lang_id)] = '+'

    # 3) Costruisco righe pronte per il template
    rows = []
    for p in parameters:
        cells = []
        for lang in languages:
            cells.append(px.get((p.id, lang.id), ""))  # "" se mancante
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
