from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from .models import Language
from .services.param_graph import (
    get_param_graph_payload,
    get_param_graph_payload_for_language,  
)


def param_graph_page(request):
    """
    Pagina grafo: ora riceve l'elenco lingue per popolare il <select>.
    """
    languages = Language.objects.order_by("id")
    preselect = request.GET.get("lang") or ""
    return render(request, "graphs/param_graph.html", {
        "languages": languages,
        "preselect": preselect,
    })

def param_graph_json(request):
    """
    Payload strutturale (solo nodi/archi/condizioni). Rimane per retrocompatibilità.
    """
    payload = get_param_graph_payload()
    return JsonResponse(payload, safe=False)

def param_graph_json_for_language(request, lang_id: str):
    """
    Payload completo per lingua: nodi con value/color/tooltip e archi.
    Tutta la logica e i dati vengono dal backend (db + funzioni), non dal JS.
    """
    get_object_or_404(Language, id=lang_id)
    payload = get_param_graph_payload_for_language(lang_id)
    return JsonResponse(payload, safe=False)
