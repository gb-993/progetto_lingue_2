from __future__ import annotations
from typing import Any, Dict, Tuple

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import render
from django.utils.translation import gettext as _

from core.models import (
    User, Language, ParameterDef, Question, Answer, Example,
    Motivation, AnswerMotivation, QuestionAllowedMotivation,
    LanguageParameter,
)

try:
    from core.models import LanguageParameterEval
    HAS_EVAL = True
except Exception:
    LanguageParameterEval = None  # type: ignore
    HAS_EVAL = False

from .forms import (
    BaseFilterForm, UserFilterForm, LanguageFilterForm, ParameterFilterForm,
    QuestionFilterForm, AnswerFilterForm, ExampleFilterForm,
    MotivationFilterForm, LangParamFilterForm,
)

def _is_linguist_or_admin(u: User) -> bool:
    if not u.is_authenticated:
        return False
    role = getattr(u, "role", "")
    return u.is_staff or role in {"admin", "linguist"}

FORM_BY_DATASET = {
    "user":      UserFilterForm,
    "language":  LanguageFilterForm,
    "parameter": ParameterFilterForm,
    "question":  QuestionFilterForm,
    "answer":    AnswerFilterForm,
    "example":   ExampleFilterForm,
    "motivation":MotivationFilterForm,
    "langparam": LangParamFilterForm,
}

# ----------------- Query builders (sicuri) -----------------
def build_user_qs(data: Dict[str, Any]):
    qs = User.objects.all().order_by("email")
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(name__icontains=q) | Q(surname__icontains=q))
    role = data.get("role") or ""
    if role:
        qs = qs.filter(role=role)
    v = data.get("is_active")
    if v in {"1","0"}:
        qs = qs.filter(is_active=(v=="1"))
    v = data.get("is_staff")
    if v in {"1","0"}:
        qs = qs.filter(is_staff=(v=="1"))

    # Lingue assegnate (FK) esistono?
    v = data.get("has_assigned_languages")
    if v in {"1","0"}:
        sub = Language.objects.filter(assigned_user=OuterRef("pk"))
        qs = qs.annotate(_has_fk=Exists(sub))
        qs = qs.filter(_has_fk=(v=="1"))

    # Lingue M2M esistono?
    v = data.get("has_m2m_languages")
    if v in {"1","0"}:
        sub = Language.objects.filter(users__id=OuterRef("pk"))
        qs = qs.annotate(_has_m2m=Exists(sub))
        qs = qs.filter(_has_m2m=(v=="1"))

    # Ha risposte su lingue dell’utente?
    v = data.get("has_answers_on_languages")
    if v in {"1","0"}:
        sub = Answer.objects.filter(language__in=Language.objects.filter(
            Q(assigned_user=OuterRef("pk")) | Q(users__id=OuterRef("pk"))
        ))
        qs = qs.annotate(_has_ans=Exists(sub))
        qs = qs.filter(_has_ans=(v=="1"))

    # Ha submission?
    v = data.get("has_submissions")
    if v in {"1","0"}:
        from core.models import Submission
        sub = Submission.objects.filter(submitted_by=OuterRef("pk"))
        qs = qs.annotate(_has_sub=Exists(sub)).filter(_has_sub=(v=="1"))

    return qs

def build_language_qs(data: Dict[str, Any]):
    qs = Language.objects.select_related("assigned_user").order_by("position")
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(name_full__icontains=q) | Q(id__icontains=q))
    for f in ("grp","isocode","glottocode"):
        val = (data.get(f) or "").strip()
        if val:
            qs = qs.filter(**{f+"__icontains": val})
    if data.get("assigned_user"):
        qs = qs.filter(assigned_user=data["assigned_user"])
    v = data.get("has_answers")
    if v in {"1","0"}:
        sub = Answer.objects.filter(language=OuterRef("pk"))
        qs = qs.annotate(_has_ans=Exists(sub)).filter(_has_ans=(v=="1"))
    v = data.get("has_params")
    if v in {"1","0"}:
        sub = LanguageParameter.objects.filter(language=OuterRef("pk")).exclude(value_orig__isnull=True)
        qs = qs.annotate(_has_par=Exists(sub)).filter(_has_par=(v=="1"))
    return qs

def build_parameter_qs(data: Dict[str, Any]):
    qs = ParameterDef.objects.all().order_by("position")
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(id__icontains=q))
    v = data.get("is_active")
    if v in {"1","0"}:
        qs = qs.filter(is_active=(v=="1"))
    v = data.get("has_questions")
    if v in {"1","0"}:
        sub = Question.objects.filter(parameter=OuterRef("pk"))
        qs = qs.annotate(_has_q=Exists(sub)).filter(_has_q=(v=="1"))
    return qs

def build_question_qs(data: Dict[str, Any]):
    qs = Question.objects.select_related("parameter").order_by("id")
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(text__icontains=q) | Q(instruction__icontains=q))
    if data.get("parameter"):
        qs = qs.filter(parameter=data["parameter"])
    v = data.get("is_stop")
    if v in {"1","0"}:
        qs = qs.filter(is_stop_question=(v=="1"))
    v = data.get("has_answers")
    if v in {"1","0"}:
        sub = Answer.objects.filter(question=OuterRef("pk"))
        qs = qs.annotate(_has_a=Exists(sub)).filter(_has_a=(v=="1"))
    v = data.get("has_allowed_motiv")
    if v in {"1","0"}:
        sub = QuestionAllowedMotivation.objects.filter(question=OuterRef("pk"))
        qs = qs.annotate(_has_m=Exists(sub)).filter(_has_m=(v=="1"))
    return qs

def build_answer_qs(data: Dict[str, Any]):
    qs = Answer.objects.select_related("language","question").order_by("id")
    if data.get("language"):
        qs = qs.filter(language=data["language"])
    if data.get("question"):
        qs = qs.filter(question=data["question"])
    v = data.get("response_text")
    if v:
        qs = qs.filter(response_text=v)
    v = data.get("status")
    if v:
        qs = qs.filter(status=v)
    v = data.get("has_examples")
    if v in {"1","0"}:
        sub = Example.objects.filter(answer=OuterRef("pk"))
        qs = qs.annotate(_h_ex=Exists(sub)).filter(_h_ex=(v=="1"))
    v = data.get("has_motivations")
    if v in {"1","0"}:
        sub = AnswerMotivation.objects.filter(answer=OuterRef("pk"))
        qs = qs.annotate(_h_m=Exists(sub)).filter(_h_m=(v=="1"))
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(comments__icontains=q))
    return qs

def build_example_qs(data: Dict[str, Any]):
    qs = Example.objects.select_related("answer","answer__language","answer__question").order_by("id")
    v = data.get("has_gloss")
    if v in {"1","0"}:
        qs = qs.filter(gloss__isnull=(v=="0")).exclude(gloss="") if v=="1" else qs.filter(Q(gloss__isnull=True) | Q(gloss=""))
    v = data.get("has_translation")
    if v in {"1","0"}:
        qs = qs.filter(translation__isnull=(v=="0")).exclude(translation="") if v=="1" else qs.filter(Q(translation__isnull=True) | Q(translation=""))
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(gloss__icontains=q) | Q(translation__icontains=q) | Q(reference__icontains=q))
    return qs

def build_motivation_qs(data: Dict[str, Any]):
    qs = Motivation.objects.all().order_by("code")
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(label__icontains=q))
    v = data.get("used_in_answers")
    if v in {"1","0"}:
        sub = AnswerMotivation.objects.filter(motivation=OuterRef("pk"))
        qs = qs.annotate(_u=Exists(sub)).filter(_u=(v=="1"))
    v = data.get("allowed_in_questions")
    if v in {"1","0"}:
        sub = QuestionAllowedMotivation.objects.filter(motivation=OuterRef("pk"))
        qs = qs.annotate(_a=Exists(sub)).filter(_a=(v=="1"))
    return qs

def build_langparam_qs(data: Dict[str, Any]):
    qs = LanguageParameter.objects.select_related("language","parameter").order_by("language__position","parameter__position")
    if data.get("parameter"):
        qs = qs.filter(parameter=data["parameter"])
    v = data.get("value_orig")
    if v:
        if v == "null":
            qs = qs.filter(value_orig__isnull=True)
        else:
            qs = qs.filter(value_orig=v)
    v = data.get("warning_orig")
    if v in {"1","0"}:
        qs = qs.filter(warning_orig=(v=="1"))
    if HAS_EVAL:
        v = data.get("value_eval")
        if v:
            sub = LanguageParameterEval.objects.filter(language=OuterRef("language_id"),
                                                       parameter=OuterRef("parameter_id"),
                                                       value_eval=v)
            qs = qs.annotate(_ve=Exists(sub)).filter(_ve=True)
        v = data.get("warning_eval")
        if v in {"1","0"}:
            sub = LanguageParameterEval.objects.filter(language=OuterRef("language_id"),
                                                       parameter=OuterRef("parameter_id"),
                                                       warning_eval=(v=="1"))
            qs = qs.annotate(_we=Exists(sub)).filter(_we=True)
    q = (data.get("q_name") or "").strip()
    if q:
        qs = qs.filter(Q(language__name_full__icontains=q) | Q(parameter__name__icontains=q))
    return qs

BUILDERS = {
    "user": build_user_qs,
    "language": build_language_qs,
    "parameter": build_parameter_qs,
    "question": build_question_qs,
    "answer": build_answer_qs,
    "example": build_example_qs,
    "motivation": build_motivation_qs,
    "langparam": build_langparam_qs,
}

@login_required
@user_passes_test(_is_linguist_or_admin)
def search_home(request):
    dataset = request.GET.get("dataset") or "language"
    FormCls = FORM_BY_DATASET.get(dataset, LanguageFilterForm)

    form = FormCls(request.GET or None)
    qs = None
    if form.is_valid():
        data = form.cleaned_data
        qs = BUILDERS[dataset](data)

    page = int(request.GET.get("page") or 1)
    paginator = Paginator(qs or [], 25)  # 25 per pagina
    page_obj = paginator.get_page(page)

    # colonne minime per dataset (puoi estendere)
    columns_by_ds = {
        "user": ["email", "role", "is_staff", "is_active"],
        "language": ["id", "name_full", "grp", "isocode", "glottocode", "assigned_user"],
        "parameter": ["id", "name", "is_active", "position"],
        "question": ["id", "parameter", "is_stop_question"],
        "answer": ["id", "language", "question", "response_text", "status"],
        "example": ["id", "answer", "gloss", "translation"],
        "motivation": ["code", "label"],
        "langparam": ["language", "parameter", "value_orig", "warning_orig"],
    }
    columns = columns_by_ds.get(dataset, [])

    return render(request, "queries/home.html", {
        "form": form,
        "dataset": dataset,
        "page_obj": page_obj,
        "columns": columns,
    })
