# core/services/dag_eval.py
from __future__ import annotations
from collections import defaultdict, deque
import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from django.db import transaction
from django.db.models import Q

from core.models import (
    Language, ParameterDef, LanguageParameter, LanguageParameterEval
)
from .logic_parser import evaluate_with_parser

# Token parametri nelle condizioni: +FGM, -SCO, 0ABC
TOKEN_RE = re.compile(r"[+\-0]([A-Z0-9_]+)")

@dataclass
class DagReport:
    language_id: str
    processed: list[str]
    forced_zero: list[str]
    missing_orig: list[str]
    warnings_propagated: list[str]

def _active_parameter_ids() -> Set[str]:
    return set(
        ParameterDef.objects.filter(is_active=True).values_list("id", flat=True)
    )

def _extract_refs(cond: str) -> Set[str]:
    return set(TOKEN_RE.findall(cond or ""))

def _build_graph_active_scope(active_ids: Set[str]) -> Dict[str, List[str]]:
    """
    Crea grafo ref -> target SOLO per param attivi.
    Target = ogni ParameterDef attivo con una implicational_condition valida i cui ref sono tutti attivi.
    """
    graph: Dict[str, List[str]] = {pid: [] for pid in active_ids}
    qs = ParameterDef.objects.filter(is_active=True).only("id", "implicational_condition")

    for p in qs:
        cond = p.implicational_condition or ""
        if not cond.strip():
            continue  # nessuna condizione => nessun arco in entrata

        refs = _extract_refs(cond)
        if not refs:
            continue
        # Se la cond cita parametri fuori scope, ignoriamo completamente la regola (come in Flask)
        if not refs.issubset(active_ids):
            continue

        for r in refs:
            if p.id not in graph[r]:
                graph[r].append(p.id)

    return graph

def _topo_sort(graph: Dict[str, List[str]]) -> List[str]:
    indeg = {n: 0 for n in graph}
    for u, outs in graph.items():
        for v in outs:
            indeg[v] = indeg.get(v, 0) + 1

    q = deque([n for n, d in indeg.items() if d == 0])
    order: List[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in graph.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    if len(order) < len(indeg):
        # cicli: metti in coda i rimanenti
        order.extend([n for n in indeg if n not in order])
    return order

def _collect_param_values_orig(lang: Language, active_ids: Set[str]) -> Dict[str, str | None]:
    """
    Mappa param_id -> '+', '-', None (indeterminato). Solo per param attivi.
    """
    values: Dict[str, str | None] = {pid: None for pid in active_ids}
    lps = (
        LanguageParameter.objects
        .filter(language=lang, parameter_id__in=active_ids)
        .values_list("parameter_id", "value_orig")
    )
    for pid, v in lps:
        values[pid] = v  # v è '+', '-', oppure None
    return values

def _ensure_eval_row(lang: Language, pid: string, lp_id: int | None) -> LanguageParameterEval:
    """
    Garantisce una LanguageParameterEval associata al LanguageParameter esistente.
    Se lp_id è None (cioè non esiste LP per quel parametro), la creiamo ad-hoc creando prima il LP con value_orig=None.
    """
    if lp_id is None:
        lp = LanguageParameter.objects.create(language=lang, parameter_id=pid, value_orig=None, warning_orig=False)
    else:
        from core.models import LanguageParameter as LP
        lp = LP.objects.get(pk=lp_id)
    lpe, _ = LanguageParameterEval.objects.get_or_create(language_parameter=lp, defaults={"value_eval": "0", "warning_eval": False})
    return lpe

def _refs_for_target(target: str) -> Set[str]:
    cond = (ParameterDef.objects.only("implicational_condition")
            .get(pk=target).implicational_condition or "")
    return _extract_refs(cond)

@transaction.atomic
def run_dag_for_language(language_id: str) -> DagReport:
    """
    Admin-step: applica le implicational condition nello scope attivo.
    - Se la condizione del target è FALSA => value_eval = '0'
    - Se VERA => value_eval = value_orig (di quel target)
    - Non esiste auto-propagazione dello '0' oltre alle regole esplicite.
    - WARNING: si propaga: se una ref è in warning_orig/valutato, i target diventano warning_eval=True.

    Vincolo operativo (coerente con tua idea): conviene che TUTTI i parametri attivi abbiano value_orig non NULL.
    Se mancano, li elenchiamo in report.missing_orig ma procediamo comunque (quelle cond risulteranno FALSE).
    """
    lang = Language.objects.select_for_update().get(pk=language_id)
    active_ids = _active_parameter_ids()

    # valori originali (+, -, None)
    orig_values = _collect_param_values_orig(lang, active_ids)

    # grafo e ordine
    graph = _build_graph_active_scope(active_ids)
    order = _topo_sort(graph)

    # warning set per propagazione
    # partenza: warning_orig del LP; se LP mancante, non warning
    warnings: Set[str] = set(
        LanguageParameter.objects.filter(language=lang, parameter_id__in=active_ids, warning_orig=True)
        .values_list("parameter_id", flat=True)
    )

    processed: list[str] = []
    forced_zero: list[str] = []
    missing_orig: list[str] = [pid for pid, v in orig_values.items() if v is None]
    warnings_propagated: set[str] = set()

    # Pre-carichiamo mappa param_id -> (lp_id, value_orig)
    lp_map: dict[str, Tuple[int | None, str | None]] = {pid: (None, orig_values[pid]) for pid in active_ids}
    for lp in LanguageParameter.objects.filter(language=lang, parameter_id__in=active_ids).only("id", "parameter_id", "value_orig"):
        lp_map[lp.parameter_id] = (lp.id, lp.value_orig)

    # Valori "correnti" da passare al parser durante l'analisi delle condizioni:
    # usiamo '+','-' e '0' come stato "non allineato" quando manca l'orig.
    # Nota: qui scegliamo di trattare None come '0' nel contesto delle cond, così
    # una cond che richiede '+X' fallisce se X non è determinato.
    cond_values: dict[str, str] = {}
    for pid, (_, v) in lp_map.items():
        cond_values[pid] = v if v in ("+", "-") else "0"

    # Mappa target->cond
    cond_map: dict[str, str] = {
        p.id: (p.implicational_condition or "") for p in ParameterDef.objects.filter(id__in=active_ids)
    }

    # Valutazione: visitiamo tutti, ma un target senza cond resta a value_orig
    for target in order:
        # ensure eval row exists
        lp_id, v_orig = lp_map[target]
        lpe = _ensure_eval_row(lang, target, lp_id)

        cond = (cond_map.get(target) or "").strip()
        if not cond:
            # Nessuna condizione: eval = orig (se None → '0' per rispettare il check della tabella eval)
            lpe.value_eval = v_orig if v_orig in ("+", "-") else "0"
            # warning_eval = warning_orig o warning ereditato
            lpe.warning_eval = (target in warnings)
            lpe.save(update_fields=["value_eval", "warning_eval"])
            processed.append(target)
            # Propagazione warning: se target è warning, i suoi dipendenti lo erediteranno di seguito
            continue

        # Valuta condizione con i valori correnti
        cond_ok = evaluate_with_parser(cond, cond_values)
        if not cond_ok:
            # forza zero
            if lpe.value_eval != "0":
                lpe.value_eval = "0"
                lpe.save(update_fields=["value_eval"])
            forced_zero.append(target)
        else:
            # cond vera: mantieni l'originale (+/-), se non c'è orig → '0'
            lpe.value_eval = v_orig if v_orig in ("+", "-") else "0"
            lpe.save(update_fields=["value_eval"])

        # Propagazione warning: se una QUALSIASI ref è warning → target warning
        refs = _extract_refs(cond)
        if any(r in warnings for r in refs):
            if target not in warnings:
                warnings.add(target)
                warnings_propagated.add(target)

        lpe.warning_eval = (target in warnings)
        lpe.save(update_fields=["warning_eval"])
        processed.append(target)

        # Aggiorna cond_values del target per eventuali nodi a valle (anche se non serve spesso)
        cond_values[target] = lpe.value_eval

    return DagReport(
        language_id=language_id,
        processed=processed,
        forced_zero=forced_zero,
        missing_orig=missing_orig,
        warnings_propagated=sorted(warnings_propagated),
    )
