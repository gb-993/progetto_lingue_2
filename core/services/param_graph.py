# core/services/param_graph.py
from __future__ import annotations
from collections import deque
import re
from typing import Dict, List, Set, Tuple

from django.db.models import QuerySet

from core.models import ParameterDef
from core.services.logic_parser import pretty_print_expression  # per tooltip "umano"

# Stessa logica di riconoscimento token del DAG (senza importare internals)
TOKEN_RE = re.compile(r"[+\-0]([A-Za-z0-9_]+)")

def _extract_refs(cond: str) -> Set[str]:
    return {m.upper() for m in TOKEN_RE.findall(cond or "")}

def _active_ids() -> Set[str]:
    return set(
        ParameterDef.objects.filter(is_active=True).values_list("id", flat=True)
    )

def _build_graph(active_ids: Set[str]) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """
    Ritorna:
      - adjacency: ref -> [target,...]
      - cond_map: target -> condizione originale (stringa)
    Nota: ignora condizioni che citano param fuori dallo scope attivo (coerente al DAG).
    """
    adjacency: Dict[str, List[str]] = {pid: [] for pid in active_ids}
    cond_map: Dict[str, str] = {}

    qs: QuerySet[ParameterDef] = ParameterDef.objects.filter(is_active=True).only("id", "implicational_condition")
    for p in qs:
        cond = (p.implicational_condition or "").strip()
        if not cond:
            cond_map[p.id] = ""
            continue
        refs = _extract_refs(cond)
        if not refs:
            cond_map[p.id] = cond
            continue
        # se la condizione cita param non attivi: salta (coerente a _build_graph_active_scope)
        if not refs.issubset(active_ids):
            cond_map[p.id] = cond
            continue
        for r in refs:
            if p.id not in adjacency[r]:
                adjacency[r].append(p.id)
        cond_map[p.id] = cond
    return adjacency, cond_map

def _topo_levels(adjacency: Dict[str, List[str]]) -> Dict[str, int]:
    """
    Assegna un 'livello' topologico (rank) per layout layered.
    Kahn + tracking livelli.
    """
    indeg: Dict[str, int] = {n: 0 for n in adjacency}
    for u, outs in adjacency.items():
        for v in outs:
            indeg[v] = indeg.get(v, 0) + 1

    q = deque([n for n, d in indeg.items() if d == 0])
    level: Dict[str, int] = {n: 0 for n in q}

    while q:
        u = q.popleft()
        for v in adjacency.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                level[v] = level.get(u, 0) + 1
                q.append(v)

    # per eventuali cicli residui: assegna l'ultimo livello +1
    if len(level) < len(adjacency):
        maxlvl = max(level.values()) if level else 0
        for n in indeg:
            if n not in level:
                level[n] = maxlvl + 1
    return level

def get_param_graph_payload() -> dict:
    """
    Restituisce payload JSON:
      {
        "nodes": [{"id": "FGM", "label": "FGM", "rank": 0, "cond_human": "(...)"}, ...],
        "edges": [{"source": "FGM", "target": "ABC"}, ...],
        "meta": {"active_count": N, "has_edges": true/false}
      }
    """
    active = _active_ids()
    adjacency, cond_map = _build_graph(active)
    levels = _topo_levels(adjacency)

    nodes = []
    for pid in sorted(active):  # ordinamento stabile per riproducibilità
        cond = cond_map.get(pid, "")
        # pretty per tooltip; se invalida, lascia vuoto
        try:
            cond_h = pretty_print_expression(cond) if cond else ""
        except Exception:
            cond_h = cond or ""
        nodes.append({
            "id": pid,
            "label": pid,      # label breve: id; puoi cambiare in name se vuoi
            "rank": int(levels.get(pid, 0)),
            "cond": cond or "",
            "cond_human": cond_h,
        })

    edges = []
    for u, outs in adjacency.items():
        for v in outs:
            edges.append({"source": u, "target": v})

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "active_count": len(active),
            "has_edges": any(edges),
        }
    }
