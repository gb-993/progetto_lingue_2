# core/services/dag_debug.py
from __future__ import annotations
from typing import Dict, Tuple, List, Optional, Set
from django.db.models import QuerySet
from core.models import Language, ParameterDef, LanguageParameter
from core.services.logic_parser import evaluate_with_parser, pretty_print_expression

def build_cond_values_for_language(lang: Language, active_ids: Set[str]) -> Dict[str, str]:
    """
    Crea la mappa param_id -> '+','-','0' per valutare le condizioni,
    replicando la logica del DAG: None => '0'.
    """
    vals: Dict[str, str] = {pid: "0" for pid in active_ids}
    for pid, v in (LanguageParameter.objects
                   .filter(language=lang, parameter_id__in=active_ids)
                   .values_list("parameter_id", "value_orig")):
        vals[pid] = v if v in ("+","-") else "0"
    return vals

def diagnostics_for_language(lang: Language) -> List[dict]:
    """
    Ritorna, per ogni parametro ATTIVO, una riga diagnostica:
      - param_id
      - cond_raw (stringa salvata)
      - cond_pretty (forma leggibile tipo "(FGM=+ OR FGA=+) AND FGK=-")
      - eval_with_current_values: True/False (cioè VERA/FALSA)
      - value_orig (se c'è)
      - value_eval (se presente la riga di eval)
      - note (eventuali warning: missing orig, ecc.)
    """
    active_params: QuerySet[ParameterDef] = ParameterDef.objects.filter(is_active=True).only("id","implicational_condition","position").order_by("position","id")
    active_ids = set(active_params.values_list("id", flat=True))
    cond_values = build_cond_values_for_language(lang, active_ids)

    # mappa rapida orig/eval
    lp_by_pid = {pid: (None, None) for pid in active_ids}  
    for pid, v in (LanguageParameter.objects
                   .filter(language=lang, parameter_id__in=active_ids)
                   .values_list("parameter_id", "value_orig")):
        lp_by_pid[pid] = (v, lp_by_pid[pid][1])
    # eval (se c'è)
    try:
        from core.models import LanguageParameterEval
        for pid, ve in (LanguageParameterEval.objects
                        .filter(language_parameter__language=lang,
                                language_parameter__parameter_id__in=active_ids)
                        .values_list("language_parameter__parameter_id","value_eval")):
            lp_by_pid[pid] = (lp_by_pid[pid][0], ve)
    except Exception:
        pass

    rows: List[dict] = []
    for p in active_params:
        raw = (p.implicational_condition or "").strip()
        pretty = ""
        ok = None
        note = ""
        if not raw:
            pretty = "—"
            ok = True  # (il DAG copia l’orig)
        else:
            try:
                pretty = pretty_print_expression(raw)
                ok = bool(evaluate_with_parser(raw, cond_values))
            except Exception as e:
                pretty = "(parse error)"
                ok = False
                note = f"Parse error: {e!s}"

        v_orig, v_eval = lp_by_pid.get(p.id, (None, None))
        if v_orig is None:
            # nel DAG: None viene trattato come '0' dentro alle condizioni
            if not note:
                note = "value_orig=None → in condizioni vale '0'"

        rows.append({
            "param_id": p.id,
            "cond_raw": raw or "—",
            "cond_pretty": pretty,
            "cond_true": ok,               
            "value_orig": (v_orig if v_orig is not None else ""),
            "value_eval": (v_eval if v_eval is not None else ""),
            "note": note,
        })
    return rows
