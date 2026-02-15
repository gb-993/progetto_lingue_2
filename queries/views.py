from __future__ import annotations
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from core.services.logic_parser import _as_list
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from core.services.logic_parser import build_parser
from core.models import (
    Language, ParameterDef, LanguageParameter, LanguageParameterEval, Answer,
)
from core.services.logic_parser import evaluate_with_parser, pretty_print_expression 
import re
from .forms import (
    ParamPickForm, ParamNeutralizationForm, LangOnlyForm, LangPairForm
)


def _is_linguist_or_admin(u) -> bool:
    if not u.is_authenticated:
        return False
    role = getattr(u, "role", "")
    return u.is_staff or role in {"admin", "linguist"}


TOKEN_RE = re.compile(r'([+\-0])([A-Za-z][A-Za-z0-9_]*)')

def extract_tokens(expr: str) -> List[Tuple[str, str]]:
    return TOKEN_RE.findall((expr or "").strip().upper())

def safe_pretty(expr: str) -> str:
    s = (expr or "").strip()
    if not s:
        return ""
    try:
        return pretty_print_expression(s)
    except Exception:
        return (expr or "")



@dataclass
class FinalValue:
    value: str | None  

def final_value_for(lang_id: str, param_id: str) -> FinalValue:
    lpe = (
        LanguageParameterEval.objects
        .filter(language_parameter__language_id=lang_id,
                language_parameter__parameter_id=param_id)
        .only("value_eval")
        .first()
    )
    if lpe and lpe.value_eval in {"+", "-", "0"}:
        return FinalValue(lpe.value_eval)

    lp = (
        LanguageParameter.objects
        .filter(language_id=lang_id, parameter_id=param_id)
        .only("value_orig")
        .first()
    )
    return FinalValue(lp.value_orig if lp else None)

def final_map_for_language(lang: Language) -> Dict[str, str | None]:

    out: Dict[str, str | None] = {}
    for lpe in LanguageParameterEval.objects.filter(language_parameter__language=lang)\
                                           .select_related("language_parameter"):
        out[lpe.language_parameter.parameter_id] = lpe.value_eval
    for lp in LanguageParameter.objects.filter(language=lang).only("parameter_id", "value_orig"):
        out.setdefault(lp.parameter_id, lp.value_orig)
    return out


def explain_logic_evaluation(expression: str, values: dict[str, str]):
    """
    Analizza l'espressione e restituisce una lista di passaggi logici
    per spiegare come si è arrivati al risultato finale.
    """
    parser = build_parser()  # Usa il parser già esistente
    steps = []

    def node_to_str(n):
        """Ricostruisce una stringa leggibile da un nodo del parser."""
        if isinstance(n, tuple):
            return f"{n[0]}{n[1]}"
        if isinstance(n, list):
            if len(n) == 2 and str(n[0]).lower() == 'not':
                return f"NOT({node_to_str(n[1])})"
            if len(n) >= 3:
                parts = [node_to_str(n[i]) if i % 2 == 0 else str(n[i]).upper() for i in range(len(n))]
                return "(" + " ".join(parts) + ")"
        return str(n)

    def trace_eval(node, values, steps):
        # Caso 1: Token foglia (+FGM, -FGA, etc.)
        if isinstance(node, tuple):
            sign, param = node
            actual_val = values.get(param)
            # Gestione valore nullo/mancante
            display_val = actual_val if actual_val is not None else "NON DEFINITO"
            result = (actual_val == sign)

            steps.append({
                "componente": f"{sign}{param}",
                "operazione": f"Controllo se {param} ({display_val}) è uguale a '{sign}'",
                "risultato": result
            })
            return result

        node = _as_list(node)

        # Caso 2: Operatore NOT
        if isinstance(node, list) and len(node) == 2 and str(node[0]).lower() == 'not':
            inner_res = trace_eval(node[1], values, steps)
            result = not inner_res
            steps.append({
                "componente": node_to_str(node),
                "operazione": f"Inverto il risultato precedente (NOT {inner_res})",
                "risultato": result
            })
            return result

        # Caso 3: Catene di AND / OR
        if isinstance(node, list) and len(node) >= 3:
            current_expr_str = node_to_str(node[0])
            res = trace_eval(node[0], values, steps)

            i = 1
            while i < len(node):
                op = str(node[i]).lower()
                op_label = "AND" if op in ('&', 'and') else "OR"
                right_node = node[i + 1]
                right_expr_str = node_to_str(right_node)

                right_res = trace_eval(right_node, values, steps)

                old_res = res
                if op in ('&', 'and'):
                    res = res and right_res
                else:
                    res = res or right_res

                combined_expr = f"({current_expr_str} {op_label} {right_expr_str})"
                steps.append({
                    "componente": combined_expr,
                    "operazione": f"Eseguo {old_res} {op_label} {right_res}",
                    "risultato": res
                })
                current_expr_str = combined_expr
                i += 2
            return res
        return False

    try:
        parsed = parser.parseString(expression or "", parseAll=True)
        if not parsed:
            return [], True
        final_result = trace_eval(parsed[0], values, steps)
        return steps, final_result
    except Exception as e:
        return [{"errore": f"Errore di sintassi: {str(e)}"}], False


def print_circuit_diagram(node, values):
    """
    Genera una rappresentazione a circuito orizzontale (stile schema elettrico).
    Ritorna: (linee_di_testo, riga_di_connessione, risultato_booleano)
    """
    # CASO 1: Parametro (Input del circuito)
    if isinstance(node, tuple):
        sign, param = node
        val = values.get(param, "None")
        res = (val == sign)
        res_txt = "VERO" if res else "FALSO"
        # Output: "+FGM (VERO) ──"
        line = f"{sign}{param} ({res_txt}) ──"
        return [line], 0, res

    node = _as_list(node)

    # CASO 2: Operatore NOT (Invertitore)
    if len(node) == 2 and str(node[0]).lower() == 'not':
        lines, conn_idx, res_interno = print_circuit_diagram(node[1], values)
        res_finale = not res_interno
        res_txt = "VERO" if res_finale else "FALSO"

        # Estende la linea e aggiunge il NOT
        lines[conn_idx] += f"─► NOT ──► ({res_txt}) ──"
        return lines, conn_idx, res_finale

    # CASO 3: Operatori AND (&) / OR (|) (Giunzioni)
    elif len(node) >= 3:
        op_txt = str(node[1]).upper()
        if op_txt == '&': op_txt = 'AND'
        if op_txt == '|': op_txt = 'OR'

        children = [node[i] for i in range(0, len(node), 2)]
        all_blocks = []

        # Genera i blocchi per ogni figlio
        for child in children:
            all_blocks.append(print_circuit_diagram(child, values))

        # Calcolo del risultato finale del gruppo
        results = [b[2] for b in all_blocks]
        final_res = all(results) if op_txt == 'AND' else any(results)
        final_txt = "VERO" if final_res else "FALSO"

        # Assemblaggio grafico dei blocchi con le giunzioni
        output_lines = []
        conn_positions = []
        current_line = 0

        for i, (lines, conn, _) in enumerate(all_blocks):
            # Aggiunge righe vuote tra i blocchi per leggibilità
            if i > 0:
                output_lines.append("")
                current_line += 1

            # Posiziona il blocco del figlio
            for r, l in enumerate(lines):
                output_lines.append(l)
                if r == conn:
                    conn_positions.append(current_line + r)
            current_line += len(lines)

        # Disegna la giunzione verticale (la "graffa" del tuo disegno)
        min_c = min(conn_positions)
        max_c = max(conn_positions)
        mid_c = (min_c + max_c) // 2

        max_width = max(len(line) for line in output_lines)

        for r in range(len(output_lines)):
            # Allinea tutte le linee alla stessa larghezza
            if r in conn_positions:
                output_lines[r] = output_lines[r].ljust(max_width, '─')
                if r == min_c == max_c:
                    output_lines[r] += "──"
                elif r == min_c:
                    output_lines[r] += "┐ "
                elif r == max_c:
                    output_lines[r] += "┘ "
                elif r == mid_c:
                    output_lines[r] += "┤ "
                else:
                    output_lines[r] += "│ "
            elif min_c < r < max_c:
                output_lines[r] = output_lines[r].ljust(max_width)
                if r == mid_c:
                    output_lines[r] += "┼─"
                else:
                    output_lines[r] += "│ "
            else:
                output_lines[r] = output_lines[r].ljust(max_width)

        # Aggiunge l'operatore e l'esito finale
        output_lines[mid_c] += f" {op_txt} ──► {final_txt}"

        return output_lines, mid_c, final_res

def implicated_and_implicating(parameter: ParameterDef) -> Tuple[Set[str], Set[str]]:

    refs_in_param = {tok for _, tok in extract_tokens(parameter.implicational_condition or "")}

    targets_using_param: Set[str] = set()
    for p in ParameterDef.objects.exclude(pk=parameter.pk).only("id", "implicational_condition"):
        cond = (p.implicational_condition or "")
        for _, tok in extract_tokens(cond):
            if tok == parameter.pk:
                targets_using_param.add(p.pk)
                break
    return refs_in_param, targets_using_param

def language_distribution_for_param(parameter: ParameterDef) -> Dict[str, List[Language]]:

    plus, minus, zero = [], [], []

    eval_qs = LanguageParameterEval.objects.filter(
        language_parameter__parameter=parameter
    ).select_related("language_parameter__language")

    seen_langs: Set[str] = set()
    for lpe in eval_qs:
        lang = lpe.language_parameter.language
        seen_langs.add(lang.pk)
        if lpe.value_eval == "+":
            plus.append(lang)
        elif lpe.value_eval == "-":
            minus.append(lang)
        elif lpe.value_eval == "0":
            zero.append(lang)

    for lp in LanguageParameter.objects.filter(parameter=parameter)\
                                       .select_related("language"):
        if lp.language_id in seen_langs:
            continue
        if lp.value_orig == "+":
            plus.append(lp.language)
        elif lp.value_orig == "-":
            minus.append(lp.language)

    return {"+": plus, "-": minus, "0": zero}


@dataclass
class UnsatisfiedLiteral:
    sign: str  
    param_id: str
    reason: str 

def explain_neutralization(language: Language, parameter: ParameterDef) -> Dict:

    final_map = final_map_for_language(language)  
    cond = (parameter.implicational_condition or "").strip()
    tokens = extract_tokens(cond)

    
    refs = [t for (_, t) in tokens]
    zero_refs = [p for p in refs if final_map.get(p) == "0"]
    derived_by_zero = bool(zero_refs)

    
    values = {k: v for k, v in final_map.items() if v in {"+", "-", "0"}}
    cond_true = evaluate_with_parser(cond, values)

    unsatisfied: List[UnsatisfiedLiteral] = []
    if derived_by_zero:
        for z in zero_refs:
            unsatisfied.append(UnsatisfiedLiteral("0", z, "derived zero"))
    elif cond_true is False:
        for s, pid in tokens:
            v = final_map.get(pid)
            if v is None:
                unsatisfied.append(UnsatisfiedLiteral(s, pid, "unknown"))
            elif s in {"+", "-"} and v != s:
                unsatisfied.append(UnsatisfiedLiteral(s, pid, f"expected '{s}', got '{v}'"))
            elif s == "0" and v != "0":
                unsatisfied.append(UnsatisfiedLiteral(s, pid, f"expected '0', got '{v or 'None'}'"))
    return {
        "pretty": safe_pretty(cond),
        "derived_by_zero": derived_by_zero,
        "unsatisfied": unsatisfied,
    }


def comparable_params_for(lang_a: Language, lang_b: Language) -> List[Tuple[ParameterDef, str, str]]:
    """
    Parametri con valore finale determinato (+/-) in **entrambe** le lingue.
    Escludiamo '0' e None.
    """
    map_a = final_map_for_language(lang_a)
    map_b = final_map_for_language(lang_b)

    rows: List[Tuple[ParameterDef, str, str]] = []
    for p in ParameterDef.objects.filter(is_active=True).order_by("position"):
        va = map_a.get(p.pk)
        vb = map_b.get(p.pk)
        if va in {"+", "-"} and vb in {"+", "-"}:
            rows.append((p, va, vb))
    return rows


@login_required
@user_passes_test(_is_linguist_or_admin)
def home(request):

    active_tab = request.GET.get("tab") or ""

    ctx = {
        "tab": active_tab,
        "form_q1": ParamPickForm(request.GET if request.GET.get("tab") == "q1" else None),
        "form_q2": ParamPickForm(request.GET if request.GET.get("tab") == "q2" else None),
        "form_q3": ParamNeutralizationForm(request.GET if request.GET.get("tab") == "q3" else None),
        "form_q4": LangOnlyForm(request.GET if request.GET.get("tab") == "q4" else None),
        "form_q5": LangOnlyForm(request.GET if request.GET.get("tab") == "q5" else None),
        "form_q6": LangOnlyForm(request.GET if request.GET.get("tab") == "q6" else None),
        "form_q7": LangPairForm(request.GET if request.GET.get("tab") == "q7" else None),
        "form_q8": LangOnlyForm(request.GET if request.GET.get("tab") == "q8" else None),
        "form_q9": LangOnlyForm(request.GET if request.GET.get("tab") == "q9" else None),
        "q1": None, "q2": None, "q3": None, "q4": None, "q5": None, "q6": None, "q7": None, "q8": None, "q9": None,
    }

    # 1. Ordinamento alfabetico per le lingue (Query 7 e altre)
    for f_key in ["form_q3", "form_q4", "form_q5", "form_q6", "form_q7", "form_q8", "form_q9"]:
        form = ctx.get(f_key)
        if form:
            for field_name in ["language", "language_a", "language_b"]:
                if field_name in form.fields:
                    form.fields[field_name].queryset = Language.objects.all().order_by("name_full")

    if ctx["form_q1"].is_bound and ctx["form_q1"].is_valid():
        p = ctx["form_q1"].cleaned_data["parameter"]
        refs_in_param, targets_using_param = implicated_and_implicating(p)

        ctx["q1"] = {
            "parameter": p,
            "pretty_condition": safe_pretty(p.implicational_condition),
            "raw_condition": p.implicational_condition,
            "implicanti": ParameterDef.objects.filter(pk__in=refs_in_param).order_by("position"),
            "implicati": ParameterDef.objects.filter(pk__in=targets_using_param).order_by("position"),
        }
    
    if ctx["form_q2"].is_bound and ctx["form_q2"].is_valid():
        p = ctx["form_q2"].cleaned_data["parameter"]
        dist = language_distribution_for_param(p)
        ctx["q2"] = {"parameter": p, "plus": dist.get("+", []), "minus": dist.get("-", []), "zero": dist.get("0", [])}

        # In views.py, dentro la funzione home(request):

    if ctx["form_q3"].is_bound and ctx["form_q3"].is_valid():
        lang = ctx["form_q3"].cleaned_data["language"]
        p = ctx["form_q3"].cleaned_data["parameter"]

        # 1. Recupero la mappa completa dei valori della lingua (Eval > Orig)
        # Questo serve per sapere lo stato attuale di ogni dipendenza
        vals_map = final_map_for_language(lang)

        cond = (p.implicational_condition or "").strip()

        if not cond:
            ctx["q3"] = {"language": lang, "parameter": p, "no_condition": True}
        else:
            parser = build_parser()
            try:
                # 2. Parsing della condizione
                parsed_res = parser.parseString(cond, parseAll=True)

                # 3. Generazione del diagramma a circuito usando la funzione già presente
                # Passiamo i valori reali della lingua per colorare i nodi (VERO/FALSO)
                lines, _, final_result = print_circuit_diagram(parsed_res[0], vals_map)

                ctx["q3"] = {
                    "language": lang,
                    "parameter": p,
                    "condition": cond,
                    "circuit_lines": "\n".join(lines),
                    "is_neutralized": (final_result is False)
                }
            except Exception as e:
                ctx["q3"] = {"language": lang, "parameter": p, "error": str(e)}

    
    for tab, want in (("q4", "+"), ("q5", "-"), ("q6", "0")):
        form = ctx[f"form_{tab}"]
        if form.is_bound and form.is_valid():
            lang = form.cleaned_data["language"]
            fmap = final_map_for_language(lang)
            wanted_ids = [pid for pid, v in fmap.items() if v == want]
            params = list(ParameterDef.objects.filter(pk__in=wanted_ids).order_by("position"))
            if want == "0":
                rows = []
                for p in params:
                    cond = p.implicational_condition or ""
                    rows.append({
                        "parameter": p,
                        "condition": cond,
                        "pretty": safe_pretty(cond),
                    })
                ctx[tab] = {"language": lang, "rows": rows}

            else:
                ctx[tab] = {"language": lang, "params": params}

    
    if ctx["form_q7"].is_bound and ctx["form_q7"].is_valid():
        a = ctx["form_q7"].cleaned_data["language_a"]
        b = ctx["form_q7"].cleaned_data["language_b"]
        rows = comparable_params_for(a, b)
        ctx["q7"] = {"a": a, "b": b, "rows": rows}


    for tab, val in (("q8", "yes"), ("q9", "no")):
        form = ctx[f"form_{tab}"]
        if form.is_bound and form.is_valid():
            lang = form.cleaned_data["language"]
            # Filtriamo il modello Answer per lingua e testo della risposta (case-insensitive)
            answers = Answer.objects.filter(
                language=lang,
                response_text__iexact=val
            ).select_related("question__parameter").order_by("question__parameter__position", "question__id")

            ctx[tab] = {"language": lang, "answers": answers, "type": val.upper()}

    return render(request, "queries/home.html", ctx)