# core/services/dag_debug.py  [NUOVO FILE]
from __future__ import annotations
from typing import Dict, Tuple, List, Optional, Set
from django.db.models import QuerySet
from core.models import Language, ParameterDef, LanguageParameter, LanguageParameterEval
from core.services.logic_parser import evaluate_with_parser, pretty_print_expression

# ------------------------------------------------------------
# 1) ORIG → mantenuto solo per compatibilità (non più usato)
# ------------------------------------------------------------
def build_cond_values_for_language(lang: Language, active_ids: Set[str]) -> Dict[str, str]:
    """
    [DEPRECATO] Mappa param_id -> '+','-','0' costruita dagli ORIG.
    None -> '0'. Non più usata in diagnostics.
    """
    vals: Dict[str, str] = {pid: "0" for pid in active_ids}
    for pid, v in (
        LanguageParameter.objects
        .filter(language=lang, parameter_id__in=active_ids)
        .values_list("parameter_id", "value_orig")
    ):
        vals[pid] = v if v in ("+","-") else "0"
    return vals

# ------------------------------------------------------------
# 2) EVAL → nuova sorgente per il Check
# ------------------------------------------------------------
def build_cond_values_from_eval(lang: Language, active_ids: Set[str]) -> Dict[str, str]:
    """
    Costruisce la mappa param_id -> '+','-','0' a partire dai value_eval
    già calcolati dal DAG. Le referenze con value_eval NULL NON vengono inserite
    (assenza di chiave = ignoto per il parser).
    """
    vals: Dict[str, str] = {}
    for pid, ve in (
        LanguageParameterEval.objects
        .filter(language_parameter__language=lang,
                language_parameter__parameter_id__in=active_ids)
        .values_list("language_parameter__parameter_id", "value_eval")
    ):
        if ve in ("+", "-", "0"):
            vals[pid] = ve
    return vals

# ------------------------------------------------------------
# 3) Diagnostica allineata al DAG:
#    - Check calcolato SU EVAL
#    - Gli originali servono solo a mostrare cosa verrà copiato se TRUE
# ------------------------------------------------------------
def diagnostics_for_language(lang: Language) -> List[dict]:
    """
    Per ogni parametro ATTIVO, produce:
      - param_id
      - cond_raw
      - cond_pretty
      - cond_true  (Check calcolato su EVAL: True/False/None se indeterminato)
      - value_orig
      - value_eval
      - note       (missing eval refs / parse error)
    Regola chiarita: gli ORIG si usano solo quando la condizione risulta TRUE,
    perché il DAG copia value_orig in value_eval in quel caso.
    """
    active_params: QuerySet[ParameterDef] = (
        ParameterDef.objects
        .filter(is_active=True)
        .only("id", "implicational_condition", "position")
        .order_by("position", "id")
    )
    active_ids = set(active_params.values_list("id", flat=True))

    # Mappa condizioni basata sui value_eval già prodotti dal DAG
    cond_values_eval = build_cond_values_from_eval(lang, active_ids)

    # Mappa (orig, eval) per stampa
    lp_by_pid: Dict[str, Tuple[Optional[str], Optional[str]]] = {pid: (None, None) for pid in active_ids}

    for pid, v in (
        LanguageParameter.objects
        .filter(language=lang, parameter_id__in=active_ids)
        .values_list("parameter_id", "value_orig")
    ):
        lp_by_pid[pid] = (v, lp_by_pid[pid][1])

    for pid, ve in (
        LanguageParameterEval.objects
        .filter(language_parameter__language=lang,
                language_parameter__parameter_id__in=active_ids)
        .values_list("language_parameter__parameter_id","value_eval")
    ):
        lp_by_pid[pid] = (lp_by_pid[pid][0], ve)

    rows: List[dict] = []
    for p in active_params:
        raw = (p.implicational_condition or "").strip()
        pretty = ""
        cond_true: Optional[bool] = None
        note_parts: List[str] = []

        # Pretty per segnalare errori di sintassi (qui può sollevare)
        if not raw:
            pretty = "—"
            # Nessuna condizione: il DAG copia l'orig; il Check è, per convenzione, True.
            cond_true = True
        else:
            try:
                pretty = pretty_print_expression(raw)
            except Exception as e:
                pretty = "(parse error)"
                cond_true = None
                note_parts.append(f"Parse error: {e!s}")
            else:
                # Valuta SEMPRE su value_eval (allineato al DAG)
                try:
                    cond_true = bool(evaluate_with_parser(raw, cond_values_eval))
                except Exception as e:
                    # evaluate_with_parser è già robusto; ramo prudenziale
                    cond_true = None
                    note_parts.append(f"Eval error: {e!s}")

                # Se la cond è FALSE ma rileviamo che mancano alcune referenze in cond_values_eval,
                # annotiamo per chiarezza che il FALSE potrebbe derivare da refs ignote (eval mancante).
                # Heuristica: token citati non presenti in cond_values_eval.
                missing_refs = _missing_eval_refs(raw, cond_values_eval)
                if missing_refs:
                    note_parts.append(f"Missing eval for: {', '.join(sorted(missing_refs))}")

        v_orig, v_eval = lp_by_pid.get(p.id, (None, None))

        rows.append({
            "param_id": p.id,
            "cond_raw": raw or "—",
            "cond_pretty": pretty,
            "cond_true": cond_true,          # Check su EVAL
            "value_orig": (v_orig if v_orig is not None else ""),
            "value_eval": (v_eval if v_eval is not None else ""),
            "note": "; ".join(n for n in note_parts if n),
        })

    return rows

# ------------------------------------------------------------
# 4) Utilità: individua referenze senza value_eval (per note)
# ------------------------------------------------------------
import re
_TOKEN_RE = re.compile(r"[+\-0]([A-Za-z0-9_]+)")

def _missing_eval_refs(cond: str, cond_values_eval: Dict[str, str]) -> Set[str]:
    if not cond.strip():
        return set()
    cited = {m.upper() for m in _TOKEN_RE.findall(cond or "")}
    missing = {pid for pid in cited if pid not in cond_values_eval}
    return missing
