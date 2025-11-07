from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Subquery, IntegerField, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from core.models import (
    Language,
    Submission,
    SubmissionAnswer,
    SubmissionAnswerMotivation,
    SubmissionExample,
    SubmissionParam,
    ParameterDef,
    Question,
)
from .services import create_language_submission


def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


def _safe_next_url(request, fallback_name: str = "submissions_list") -> str:
    candidate = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse(fallback_name)
    return candidate if url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()) else reverse(fallback_name)


@login_required
@user_passes_test(_is_admin)
def submission_create_for_language(request, language_id):
    lang = get_object_or_404(Language, pk=language_id)
    if request.method == "POST":
        note = request.POST.get("note") or ""
        with transaction.atomic():
            res = create_language_submission(lang, request.user, note=note)
        messages.success(
            request,
            _("Submission created for %(lang)s at %(ts)s (pruned=%(p)d)") % {
                "lang": lang.id,
                "ts": res.submission.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                "p": res.pruned_count,
            },
        )
        return redirect(_safe_next_url(request))
    return render(request, "submissions/confirm_create.html", {"language": lang})

from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, IntegerField, Prefetch, Q  

@login_required
@user_passes_test(_is_admin)
def submissions_list(request):
    qs = Submission.objects.select_related("language", "submitted_by").order_by("-submitted_at", "-id")

    q = (request.GET.get("q") or "").strip()  
    if q:
        # match su id lingua (parziale, case-insensitive) OR su full name (parziale)
        qs = qs.filter(Q(language__id__icontains=q) | Q(language__name_full__icontains=q))

    submitted_by = (request.GET.get("submitted_by") or "").strip()
    if submitted_by.isdigit():
        qs = qs.filter(submitted_by_id=int(submitted_by))

    date_from = (request.GET.get("date_from") or "").strip()
    if date_from:
        qs = qs.filter(submitted_at__date__gte=date_from)

    date_to = (request.GET.get("date_to") or "").strip()
    if date_to:
        qs = qs.filter(submitted_at__date__lt=date_to)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "submissions/list.html",
        {
            "page": page,
            "q": q,  
            "submitted_by": submitted_by,
            "date_from": date_from,
            "date_to": date_to,
        },
    )

@login_required
@user_passes_test(_is_admin)
def submission_detail(request, submission_id):
    """
    Annotazioni coerenti con i modelli:
    - SubmissionAnswer.question_code (char) ↔ Question.id (pk char)
    - Question.parameter_id → ParameterDef.{position,name}
    """

    # ----- ANSWERS -----
    question_parameter_id_sq = (
        Question.objects
        .filter(pk=OuterRef("question_code"))
        .values("parameter_id")[:1]
    )


    answers_qs = (
        SubmissionAnswer.objects
        .annotate(                       
            param_id=Subquery(question_parameter_id_sq)
        )
        .annotate(                       
            param_pos=Subquery(
                ParameterDef.objects
                .filter(pk=OuterRef("param_id"))
                .values("position")[:1]
            , output_field=IntegerField()),
            param_name=Subquery(
                ParameterDef.objects
                .filter(pk=OuterRef("param_id"))
                .values("name")[:1]
            ),
        )
        .order_by("param_pos", "param_id", "question_code")
    )





    answers_prefetch = Prefetch("answers", queryset=answers_qs)

    # ----- PARAMS -----
    subparam_position_sq = (
        ParameterDef.objects
        .filter(pk=OuterRef("parameter_id"))
        .values("position")[:1]
    )
    params_prefetch = Prefetch(
        "params",
        queryset=(
            SubmissionParam.objects
            .annotate(param_pos=Subquery(subparam_position_sq, output_field=IntegerField()))
            .order_by("param_pos", "parameter_id")
        ),
    )

    # ----- MOTIVATIONS & EXAMPLES -----
    mots_prefetch = Prefetch(
        "answer_motivations",
        queryset=SubmissionAnswerMotivation.objects.order_by("question_code", "motivation_code"),
    )
    examples_prefetch = Prefetch(
        "examples",
        queryset=SubmissionExample.objects.order_by("question_code", "id"),
    )

    sub = get_object_or_404(
        Submission.objects.select_related("language", "submitted_by")
        .prefetch_related(answers_prefetch, params_prefetch, mots_prefetch, examples_prefetch),
        pk=submission_id,
    )

    # Aggregazione motivazioni per riga answer
    mot_by_q = {}
    for m in sub.answer_motivations.all():
        mot_by_q.setdefault(m.question_code, []).append(m.motivation_code)

    answers = list(sub.answers.all())
    for a in answers:
        a.mot_text = ", ".join(mot_by_q.get(a.question_code, [])) or ""

    return render(
        request,
        "submissions/detail.html",
        {
            "sub": sub,
            "sub_answers": answers,
            "sub_examples": list(sub.examples.all()),
            "sub_params": list(sub.params.all()),
        },
    )
