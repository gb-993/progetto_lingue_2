from __future__ import annotations

import re
from typing import Dict, Any, List, Set
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Modelli REALI (vedi core/models.py)
from core.models import ParameterDef, Language  # NOTA: nessun modello Implication nel tuo schema


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
    lang = request.GET.get("lang")
    if not lang:
        return HttpResponseBadRequest("Missing lang")
    try:
        language = Language.objects.get(id=lang)
    except Language.DoesNotExist:
        return HttpResponseBadRequest("Invalid lang")

    # Recupera tutti i parametri; 'is_active' è il campo reale
    params = list(
        ParameterDef.objects.all().values("id", "name", "is_active")
    )

    results: Dict[str, Dict[str, Any]] = {}

    try:
        from core.services.dag_eval import evaluate_language  
    except ImportError:
        evaluate_language = None  

    if evaluate_language is not None:  
        try:
            eval_res = evaluate_language(language)
        except Exception as e:
            # Non silenziare completamente: logga, ma continua a restituire "unset"
            import logging
            logging.getLogger(__name__).exception(
                "evaluate_language() failed for language %s", language
            )
            eval_res = None

        if isinstance(eval_res, dict):
            for k, v in eval_res.items():
                pid_key = str(k)

                if isinstance(v, dict):
                    final_val = (
                        v.get("final")
                        or v.get("final_value")
                        or v.get("value_eval")
                        or v.get("value")
                        or v.get("raw")
                        or v.get("answer")
                    )
                else:
                    final_val = v

                if final_val is None or final_val == "":
                    final_str = "unset"
                else:
                    final_str = str(final_val)

                results[pid_key] = {"final": final_str}

    # Costruzione payload in uscita
    payload: List[Dict[str, Any]] = []
    for p in params:
        pid = p["id"]
        final_val = (results.get(str(pid), {}) or {}).get("final", "unset")
        label = f'{p["id"]} — {p["name"]}' if p.get("name") else p["id"]
        payload.append(
            {
                "id": pid,
                "label": label,
                "final": final_val,           
                "active": bool(p["is_active"]),  
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
