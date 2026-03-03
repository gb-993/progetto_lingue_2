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

import logging
logger = logging.getLogger(__name__)

# per cercare Token parametri nelle condizioni: +FGM, -SCO, 0ABC
TOKEN_RE = re.compile(r"[+\-0]([A-Za-z0-9_]+)")


# fornisce un report dettagliato dell'esecuzione del DAG per una lingua, utile per debug e verifiche
@dataclass
class DagReport:
    language_id: str
    processed: list[str]
    forced_zero: list[str]
    missing_orig: list[str]
    warnings_propagated: list[str]
    parse_errors: list[tuple[str, str, str]]  



# recupera l'insieme degli id dei parametri attivi, per limitare scope del DAG e parser
def _active_parameter_ids() -> Set[str]:
    return set(
        ParameterDef.objects.filter(is_active=True).values_list("id", flat=True)
    )


# estrae i parametri e li normalizza uppercase
def _extract_refs(cond: str) -> Set[str]:
    return {m.upper() for m in TOKEN_RE.findall(cond or "")}


# crea un grafo ref -> target SOLO per param attivi e solo se tutte le condizioni sono valide
def _build_graph_active_scope(active_ids: Set[str]) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = {pid: [] for pid in active_ids}
    qs = ParameterDef.objects.filter(is_active=True).only("id", "implicational_condition")
    for p in qs:
        cond = p.implicational_condition or ""
        if not cond.strip():
            continue  # nessuna condizione -> nessun arco in entrata

        refs = _extract_refs(cond)
        if not refs:
            continue
        # Se la cond cita parametri fuori scope, ignora completamente la regola
        if not refs.issubset(active_ids):
            continue

        for r in refs:
            if p.id not in graph[r]:
                graph[r].append(p.id)

    return graph



# nessun parametro viene calcolato prima di quelli da cui dipende
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
        order.extend([n for n in indeg if n not in order])
    return order



# recupera solo i valori INSERITI DALL'UTENTE (value_orig) 
def _collect_param_values_orig(lang: Language, active_ids: Set[str]) -> Dict[str, str | None]:

    values: Dict[str, str | None] = {pid: None for pid in active_ids}
    lps = (
        LanguageParameter.objects
        .filter(language=lang, parameter_id__in=active_ids)
        .values_list("parameter_id", "value_orig")
    )
    for pid, v in lps:
        values[pid] = v  # v è '+', '-', oppure None
    return values


# Assicura che nel database esista una riga nella tabella LanguageParameterEval per ospitare il risultato del calcolo.
def _ensure_eval_row(lang: Language, pid: str, lp_id: int | None) -> LanguageParameterEval:
 
    if lp_id is None:
        lp = LanguageParameter.objects.create(language=lang, parameter_id=pid, value_orig=None, warning_orig=False)
    else:
        from core.models import LanguageParameter as LP
        lp = LP.objects.get(pk=lp_id)
    lpe, _ = LanguageParameterEval.objects.get_or_create(
        language_parameter=lp,
        defaults={"value_eval": "0", "warning_eval": False}
    )
    return lpe



@transaction.atomic
def run_dag_for_language(language_id: str) -> DagReport:
    """
    (nessuna propagazione automatica dello '0'):
    - Valuta SEMPRE la condizione con il parser, indipendentemente da eventuali ref='0'.
    - Esiti:
        * condizione VERA  → value_eval = value_orig se '+' o '-', altrimenti NULL
        * condizione FALSA → value_eval = '0'
        * condizione INDETERMINATA (parse error / ref sconosciute) → value_eval = NULL
    - Nessun forcing a '0' per la sola presenza di ref='0'.
    - Warning: si propaga se una qualsiasi referenza è in warning.
    """
    # blocca la riga del db e recupera gli id attivi
    lang = Language.objects.select_for_update().get(pk=language_id) 
    active_ids = _active_parameter_ids()

    # valori originali (+, -, None) per param attivi
    orig_values = _collect_param_values_orig(lang, active_ids)

    # crea il grafo
    graph = _build_graph_active_scope(active_ids)
    order = _topo_sort(graph)

    # warning iniziali 
    warnings: Set[str] = set(
        LanguageParameter.objects.filter(
            language=lang, parameter_id__in=active_ids, warning_orig=True
        ).values_list("parameter_id", flat=True)
    )

    # memorizza risultati per non interrogare db decine di volte
    processed: list[str] = []
    forced_zero: list[str] = []
    missing_orig: list[str] = [pid for pid, v in orig_values.items() if v is None]
    warnings_propagated: set[str] = set()
    parse_errors: list[tuple[str, str, str]] = []

    # Precarica mappa param_id -> (lp_id, value_orig)
    lp_map: dict[str, Tuple[int | None, str | None]] = {
        pid: (None, orig_values[pid]) for pid in active_ids
    }
    for lp in LanguageParameter.objects.filter(
        language=lang, parameter_id__in=active_ids
    ).only("id", "parameter_id", "value_orig"):
        lp_map[lp.parameter_id] = (lp.id, lp.value_orig)

    # Valori correnti per il parser:
    #   - SOLO '+' o '-' se noti (da value_eval già prodotti)
    #   - '0' se il parametro è già stato valutato a zero
    #   - assenza di chiave = sconosciuto/indeterminato
    cond_values: dict[str, str] = {}
    unknown_params: Set[str] = set()

    # Cache condizioni
    cond_map: dict[str, str] = {
        p.id: (p.implicational_condition or "")
        for p in ParameterDef.objects.filter(id__in=active_ids)
    }




    for target in order:
        lp_id, v_orig = lp_map[target]
        lpe = _ensure_eval_row(lang, target, lp_id)
        cond = (cond_map.get(target) or "").strip()

        # MODIFICA: Gestione parametri base (senza condizione)
        if not cond:
            # Se manca la risposta, forziamo '?' e attiviamo il warning
            if v_orig is None:
                new_eval = "?"
                if target not in warnings:
                    warnings.add(target)
            # Se c'è già un warning (conflitto), il valore diventa '?'
            elif target in warnings:
                new_eval = "?"
            else:
                new_eval = v_orig if v_orig in ("+", "-") else None

            lpe.value_eval = new_eval
            lpe.warning_eval = (target in warnings)
            lpe.save(update_fields=["value_eval", "warning_eval"])

            # Aggiornamento cond_values (includendo ora il punto di domanda)
            if new_eval in ("+", "-", "0", "?"):
                cond_values[target] = new_eval
            
            processed.append(target)
            continue

        refs = _extract_refs(cond)

        # MODIFICA: Short-circuit se i "padri" hanno un warning
        # Se una referenza è in warning (e quindi è '?'), il figlio diventa '?'
        if any(r in warnings for r in refs):
            if target not in warnings:
                warnings.add(target)
                warnings_propagated.add(target)
            
            lpe.value_eval = "?"
            lpe.warning_eval = True
            lpe.save(update_fields=["value_eval", "warning_eval"])
            
            cond_values[target] = "?"
            processed.append(target)
            continue

        # Se i padri sono puliti, interroghiamo il parser
        try:
            parsed_ok = evaluate_with_parser(cond, cond_values)
            parse_error = None
        except Exception as e:
            parsed_ok = None
            parse_error = e

        cond_ok = parsed_ok if parse_error is None else None

        # Applichiamo l'esito logico
        if cond_ok is False:
            # Condizione falsa => valore '0'
            lpe.value_eval = "0"
            forced_zero.append(target)
        elif cond_ok is True:
            # Condizione vera => usiamo il valore originale (+ o -)
            # MODIFICA: Se la risposta manca proprio quando serve alla logica, mettiamo '?'
            if v_orig is None:
                lpe.value_eval = "?"
                if target not in warnings:
                    warnings.add(target)
                    warnings_propagated.add(target)
            else:
                lpe.value_eval = v_orig
        else:
            # Errore di parsing o dati insufficienti
            lpe.value_eval = None
            if parse_error:
                parse_errors.append((target, cond, str(parse_error)))

        # MODIFICA: Check finale. Se il parametro è finito in warning, forziamo '?'
        if target in warnings:
            lpe.value_eval = "?"

        # Salvataggio finale dello stato valutato e del warning
        lpe.warning_eval = (target in warnings)
        lpe.save(update_fields=["value_eval", "warning_eval"])

        # Registrazione del valore per i parametri successivi nel DAG
        if lpe.value_eval:
            cond_values[target] = lpe.value_eval
        
        processed.append(target)

    return DagReport(
        language_id=language_id,
        processed=processed,
        forced_zero=forced_zero,
        missing_orig=missing_orig,
        warnings_propagated=sorted(warnings_propagated),
        parse_errors=parse_errors,
    )