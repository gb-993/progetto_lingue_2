from __future__ import annotations

import re
from typing import Dict, Any, List, Set
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from core.models import (
    ParameterDef,
    Language,
    LanguageParameter,
    LanguageParameterEval,  # NEW: usato per leggere value_eval
)


# --------- Helpers ---------
_TOKEN_RE = re.compile(r'(?:\bnot\s+)?([+\-0])([A-Za-z0-9_]+)\b', re.IGNORECASE)

def _extract_implicant_ids(expr: str) -> Set[str]:
    """
    Estrae gli ID dei parametri referenced in una implicational_condition.
    Esempi supportati:
      "+FGK & +CSE"
      "not +GP3 & -EAL"
      "+A and (-B or 0C)"
    Ritorna insieme di ID senza segno: {"FGK","CSE","GP3","EAL","A","B","C"}
    """
    if not expr:
        return set()
    ids = set()
    for sign, pid in _TOKEN_RE.findall(expr):
        # Ignora il segno e 'not' per il grafo: il verso è sempre "pid -> parametro_corrente"
        ids.add(pid)
    return ids


# --------- Views ---------
@login_required
def parameters_graph(request: HttpRequest):
    languages = Language.objects.all().order_by("id")
    preselect = request.GET.get("lang") or ""
    return render(request, "graphs/parameters.html", {"languages": languages, "preselect": preselect})


@login_required
def api_graph(request: HttpRequest):
    """
    Ritorna nodi (parametri attivi) e archi dedotti dalle implicational_condition.
    Nodo.data.label = "ID — name" se disponibile.
    Edge: antecedent(param citato nella condizione) -> consequent(param che ha la condizione).
    """
    # NODI: solo parametri attivi (campo reale: is_active)
    params = list(ParameterDef.objects.filter(is_active=True).values("id", "name", "implicational_condition"))

    # Mappa per rapida verifica esistenza
    param_ids = {p["id"] for p in params}

    # Costruzione nodi
    nodes = []
    for p in params:
        label = p["id"]
        nodes.append({"data": {"id": p["id"], "label": label}})

    # Costruzione archi (dedotti da implicational_condition)
    edges_set = set()
    for p in params:
        pid = p["id"]
        expr = p.get("implicational_condition") or ""
        if not expr.strip():
            continue
        antecedents = _extract_implicant_ids(expr)
        for src in antecedents:
            if src in param_ids and src != pid:
                edges_set.add((src, pid))  # src -> pid

    edges = [{"data": {"id": f"{s}->{t}", "source": s, "target": t}} for (s, t) in sorted(edges_set)]

    return JsonResponse({"nodes": nodes, "edges": edges})


@login_required
def api_lang_values(request: HttpRequest):
    """
    Valori finali post-eval per tutti i parametri (attivi e non), per una lingua.
    Output: {"language": {...}, "values": [{"id","label","final","+/-/0/unset","active":bool}]}
    """
    lang_id = request.GET.get("lang")
    if not lang_id:
        return HttpResponseBadRequest("Missing lang")

    try:
        language = Language.objects.get(id=lang_id)
    except Language.DoesNotExist:
        return HttpResponseBadRequest("Invalid lang")

    # 1) Recupera tutti i parametri (attivi e non, come prima)
    params = list(
        ParameterDef.objects.all().values("id", "name", "is_active")
    )
    param_ids = [p["id"] for p in params]

    # 2) Mappa param_id -> value_eval leggendo i risultati del DAG
    #    (LanguageParameterEval collegato a LanguageParameter per quella lingua)
    eval_map: Dict[str, str | None] = {}
    eval_qs = (
        LanguageParameterEval.objects
        .filter(language_parameter__language=language,
                language_parameter__parameter_id__in=param_ids)
        .values_list("language_parameter__parameter_id", "value_eval")
    )
    for pid, val in eval_qs:
        # val è '+', '-', '0' oppure None
        eval_map[str(pid)] = val

    # 3) Costruzione payload: se non c'è value_eval → "unset"
    payload: List[Dict[str, Any]] = []
    for p in params:
        pid = str(p["id"])
        raw_val = eval_map.get(pid)

        if raw_val in ("+", "-", "0"):
            final_val = raw_val
        else:
            # None o altro ⇒ trattato come "unset" nel grafo
            final_val = "unset"

        label = f'{p["id"]} — {p["name"]}' if p.get("name") else p["id"]

        payload.append(
            {
                "id": p["id"],
                "label": label,
                "final": final_val,                 # usato da JS per i colori
                "active": bool(p["is_active"]),     # info su parametro attivo
            }
        )

    return JsonResponse(
        {
            "language": {
                "id": language.id,
                "name": getattr(language, "name_full", str(language.id)),
            },
            "values": payload,
        }
    )
