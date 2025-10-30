from __future__ import annotations
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render

from core.services.param_graph import get_param_graph_payload

@login_required
def param_graph_page(request: HttpRequest) -> HttpResponse:
    """
    Pagina standalone con canvas del grafo.
    """
    return render(request, "graphs/param_graph.html")

@login_required
def param_graph_json(request: HttpRequest) -> JsonResponse:
    """
    API read-only: nodi/archi dei parametri attivi, in ordine topologico.
    Nessun effetto collaterale, nessuna interazione col DAG di valutazione.
    """
    payload = get_param_graph_payload()
    return JsonResponse(payload, safe=True)
