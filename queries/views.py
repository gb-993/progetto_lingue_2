from __future__ import annotations
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import render
from django.utils.translation import gettext as _

from core.models import (
    Language, ParameterDef, LanguageParameter, LanguageParameterEval,
)
from core.services.logic_parser import evaluate_with_parser, pretty_print_expression  # parser/pretty
# NOTA: useremo un semplice estrattore token come in dag_eval
import re

from .forms import (
    ParamPickForm, ParamNeutralizationForm, LangOnlyForm, LangPairForm
)

# ------------- Accesso (linguists/admin) -------------
def _is_linguist_or_admin(u) -> bool:
    if not u.is_authenticated:
        return False
    role = getattr(u, "role", "")
    return u.is_staff or role in {"admin", "linguist"}

# ------------- Token extractor per cond implicazionali (+FGM, -SCO, 0ABC) -------------
TOKEN_RE = re.compile(r'([+\-0])([A-Za-z][A-Za-z0-9_]*)')

def extract_tokens(expr: str) -> List[Tuple[str, str]]:
    return TOKEN_RE.findall((expr or "").strip().upper())

# ------------- Helper dati “finali” (+/-/0/None) -------------
@dataclass
class FinalValue:
    """Valore finale per (lingua, parametro): preferisci eval, altrimenti orig."""
    value: str | None  # '+', '-', '0' oppure None

def final_value_for(lang_id: str, param_id: str) -> FinalValue:
    # 1) prova eval
    lpe = (
        LanguageParameterEval.objects
        .filter(language_parameter__language_id=lang_id,
                language_parameter__parameter_id=param_id)
        .only("value_eval")
        .first()
    )
    if lpe and lpe.value_eval in {"+", "-", "0"}:
        return FinalValue(lpe.value_eval)

    # 2) fallback orig
    lp = (
        LanguageParameter.objects
        .filter(language_id=lang_id, parameter_id=param_id)
        .only("value_orig")
        .first()
    )
    return FinalValue(lp.value_orig if lp else None)

def final_map_for_language(lang: Language) -> Dict[str, str | None]:
    """
    Ritorna una mappa param_id -> valore finale (+/-/0/None), privilegiando eval.
    """
    out: Dict[str, str | None] = {}
    # eval noti
    for lpe in LanguageParameterEval.objects.filter(language_parameter__language=lang)\
                                           .select_related("language_parameter"):
        out[lpe.language_parameter.parameter_id] = lpe.value_eval
    # completa con orig mancanti
    for lp in LanguageParameter.objects.filter(language=lang).only("parameter_id", "value_orig"):
        out.setdefault(lp.parameter_id, lp.value_orig)
    return out

# ------------- Query #1 e #2: implicati/implicanti e distribuzione lingue -------------
def implicated_and_implicating(parameter: ParameterDef) -> Tuple[Set[str], Set[str]]:
    """
    Ritorna:
      - refs_in_param: set dei param citati nella condizione di 'parameter' (implicanti)
      - targets_using_param: set di target che citano 'parameter' (implicati da 'parameter')
    """
    # implicanti (citati dalla condizione del parametro stesso)
    refs_in_param = {tok for _, tok in extract_tokens(parameter.implicational_condition or "")}

    # implicati (altri parametri che referenziano questo)
    targets_using_param: Set[str] = set()
    for p in ParameterDef.objects.exclude(pk=parameter.pk).only("id", "implicational_condition"):
        cond = (p.implicational_condition or "")
        for _, tok in extract_tokens(cond):
            if tok == parameter.pk:
                targets_using_param.add(p.pk)
                break
    return refs_in_param, targets_using_param

def language_distribution_for_param(parameter: ParameterDef) -> Dict[str, List[Language]]:
    """
    Raggruppa le lingue in tre insiemi:
      '+': value_eval=='+'
      '-': value_eval=='-'
      '0': value_eval=='0'  (neutralizzate)
    Se manca eval, usa orig (+/-) e NON le mette tra '0'.
    """
    plus, minus, zero = [], [], []

    # Preleva direttamente da eval se presente (join su LP -> LPE)
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

    # Fallback: per le lingue senza riga eval, usa orig (+/-)
    for lp in LanguageParameter.objects.filter(parameter=parameter)\
                                       .select_related("language"):
        if lp.language_id in seen_langs:
            continue
        if lp.value_orig == "+":
            plus.append(lp.language)
        elif lp.value_orig == "-":
            minus.append(lp.language)
        # None resta fuori

    return {"+": plus, "-": minus, "0": zero}

# ------------- Query #3: perché neutralizzato (condizioni non soddisfatte) -------------
@dataclass
class UnsatisfiedLiteral:
    sign: str  # '+', '-', '0'
    param_id: str
    reason: str  # "expected '+', got '-'", "derived zero", "unknown", ...

def explain_neutralization(language: Language, parameter: ParameterDef) -> Dict:
    """
    Spiega perché value_eval == '0' per (lingua,parametro):
      - se qualsiasi riferimento ha già '0' => derivazione da zero
      - altrimenti: condizione valutata a FALSE => elenca i token non soddisfatti
    """
    final_map = final_map_for_language(language)  # param -> '+','-','0',None
    cond = (parameter.implicational_condition or "").strip()
    tokens = extract_tokens(cond)

    # 1) zero upstream?
    refs = [t for (_, t) in tokens]
    zero_refs = [p for p in refs if final_map.get(p) == "0"]
    derived_by_zero = bool(zero_refs)

    # 2) prova a valutare la condizione (dando al parser '+','-' e '0')
    values = {k: v for k, v in final_map.items() if v in {"+", "-", "0"}}
    cond_true = evaluate_with_parser(cond, values)

    unsatisfied: List[UnsatisfiedLiteral] = []
    if derived_by_zero:
        for z in zero_refs:
            unsatisfied.append(UnsatisfiedLiteral("0", z, "derived zero"))
    elif cond_true is False:
        # elenca i letterali non rispettati
        for s, pid in tokens:
            v = final_map.get(pid)
            if v is None:
                unsatisfied.append(UnsatisfiedLiteral(s, pid, "unknown"))
            elif s in {"+", "-"} and v != s:
                unsatisfied.append(UnsatisfiedLiteral(s, pid, f"expected '{s}', got '{v}'"))
            elif s == "0" and v != "0":
                unsatisfied.append(UnsatisfiedLiteral(s, pid, f"expected '0', got '{v or 'None'}'"))
    return {
        "pretty": pretty_print_expression(cond) if cond else "",
        "derived_by_zero": derived_by_zero,
        "unsatisfied": unsatisfied,
    }

# ------------- Query #7: parametri confrontabili -------------
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

# ------------- VIEW: una pagina con 7 tab -------------
@login_required
@user_passes_test(_is_linguist_or_admin)
def home(request):
    """
    UI a tab:
      1) Per parametro -> implicanti/implicati
      2) Per parametro -> lingue + / - / neutralizzate
      3) Per lingua+param -> perché neutralizzato (0)
      4) Per lingua -> elenco param con '+'
      5) Per lingua -> elenco param con '-'
      6) Per lingua -> elenco param neutralizzati + condizione
      7) Per coppia lingue -> parametri confrontabili (+/-) con valori
    """
    active_tab = request.GET.get("tab") or ""

    ctx = {
        "tab": active_tab,
        # forms
        "form_q1": ParamPickForm(request.GET if request.GET.get("tab") == "q1" else None),
        "form_q2": ParamPickForm(request.GET if request.GET.get("tab") == "q2" else None),
        "form_q3": ParamNeutralizationForm(request.GET if request.GET.get("tab") == "q3" else None),
        "form_q4": LangOnlyForm(request.GET if request.GET.get("tab") == "q4" else None),
        "form_q5": LangOnlyForm(request.GET if request.GET.get("tab") == "q5" else None),
        "form_q6": LangOnlyForm(request.GET if request.GET.get("tab") == "q6" else None),
        "form_q7": LangPairForm(request.GET if request.GET.get("tab") == "q7" else None),
        # results placeholders
        "q1": None, "q2": None, "q3": None, "q4": None, "q5": None, "q6": None, "q7": None,
    }

    # -------- Q1: Per ogni parametro, elenco implicanti/implicati --------
    if ctx["form_q1"].is_bound and ctx["form_q1"].is_valid():
        p = ctx["form_q1"].cleaned_data["parameter"]
        refs_in_param, targets_using_param = implicated_and_implicating(p)
        ctx["q1"] = {
            "parameter": p,
            "implicanti": ParameterDef.objects.filter(pk__in=refs_in_param).order_by("position"),
            "implicati": ParameterDef.objects.filter(pk__in=targets_using_param).order_by("position"),
        }

    # -------- Q2: Per parametro -> lingue + / - / neutralizzate --------
    if ctx["form_q2"].is_bound and ctx["form_q2"].is_valid():
        p = ctx["form_q2"].cleaned_data["parameter"]
        dist = language_distribution_for_param(p)
        ctx["q2"] = {"parameter": p, "plus": dist.get("+", []), "minus": dist.get("-", []), "zero": dist.get("0", [])}

    # -------- Q3: Per parametro neutralizzato in una lingua -> condizioni non soddisfatte --------
    if ctx["form_q3"].is_bound and ctx["form_q3"].is_valid():
        lang = ctx["form_q3"].cleaned_data["language"]
        p = ctx["form_q3"].cleaned_data["parameter"]
        fv = final_value_for(lang.pk, p.pk).value
        if fv != "0":
            ctx["q3"] = {"parameter": p, "language": lang, "not_zero": True}
        else:
            detail = explain_neutralization(lang, p)
            ctx["q3"] = {
                "parameter": p,
                "language": lang,
                "pretty": detail["pretty"],
                "derived_by_zero": detail["derived_by_zero"],
                "unsatisfied": detail["unsatisfied"],
            }

    # -------- Q4/Q5/Q6: Per lingua -> param fissati a + / - / neutralizzati --------
    for tab, want in (("q4", "+"), ("q5", "-"), ("q6", "0")):
        form = ctx[f"form_{tab}"]
        if form.is_bound and form.is_valid():
            lang = form.cleaned_data["language"]
            fmap = final_map_for_language(lang)
            # filtra
            wanted_ids = [pid for pid, v in fmap.items() if v == want]
            params = list(ParameterDef.objects.filter(pk__in=wanted_ids).order_by("position"))
            if want == "0":
                # Aggiungi condizione implicazionale in chiaro
                rows = [{"parameter": p, "condition": (p.implicational_condition or ""), "pretty": pretty_print_expression(p.implicational_condition or "") if p.implicational_condition else ""} for p in params]
                ctx[tab] = {"language": lang, "rows": rows}
            else:
                ctx[tab] = {"language": lang, "params": params}

    # -------- Q7: Coppia lingue -> param confrontabili (+/-) --------
    if ctx["form_q7"].is_bound and ctx["form_q7"].is_valid():
        a = ctx["form_q7"].cleaned_data["language_a"]
        b = ctx["form_q7"].cleaned_data["language_b"]
        rows = comparable_params_for(a, b)
        ctx["q7"] = {"a": a, "b": b, "rows": rows}

    return render(request, "queries/home.html", ctx)
