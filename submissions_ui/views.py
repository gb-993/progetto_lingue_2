# submissions_ui/views.py
from __future__ import annotations

from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch
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
)
from .services import create_language_submission


def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


def _safe_next_url(request, fallback_name: str = "submissions_list") -> str:
    """
    Restituisce una URL di ritorno sicura.
    Priorità: POST[next] > HTTP_REFERER > reverse(fallback_name).
    """
    candidate = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse(fallback_name)
    return candidate if url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()) else reverse(fallback_name)


@login_required
@user_passes_test(_is_admin)
def submission_create_for_language(request, language_id):
    """
    Crea una Submission per la lingua indicata.
    - GET: mostra una minima pagina di conferma (se usata).
    - POST: crea la submission in transazione e fa redirect sicuro.
    """
    lang = get_object_or_404(Language, pk=language_id)

    if request.method == "POST":
        note = request.POST.get("note") or ""
        with transaction.atomic():
            res = create_language_submission(lang, request.user, note=note)

        messages.success(
            request,
            _("Submission creata per %(lang)s alle %(ts)s (pruned=%(p)d)") % {
                "lang": lang.id,
                "ts": res.submission.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                "p": res.pruned_count,
            },
        )
        return redirect(_safe_next_url(request))

    # GET: pagina di conferma minimale
    return render(request, "submissions/confirm_create.html", {"language": lang})


@login_required
@user_passes_test(_is_admin)
def submissions_list(request):
    """
    Lista submission con filtri basilari:
      - language: id lingua es. 'Sic'
      - submitted_by: id utente (int)
      - date_from/date_to: ISO YYYY-MM-DD (inclusivo/esclusivo)
    """
    qs = Submission.objects.select_related("language", "submitted_by").order_by("-submitted_at", "-id")

    language_id = (request.GET.get("language") or "").strip()
    if language_id:
        qs = qs.filter(language_id=language_id)

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

    ctx = {
        "page": page,
        "language_id": language_id,
        "submitted_by": submitted_by,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render(request, "submissions/list.html", ctx)

@login_required
@user_passes_test(_is_admin)
def submission_detail(request, submission_id):
    """
    Detail con prefetch e ordinamenti DB-side sui model concreti.
    """
    answers_prefetch = Prefetch(
        "answers",
        queryset=SubmissionAnswer.objects.order_by("question_code"),
    )
    params_prefetch = Prefetch(
        "params",
        queryset=SubmissionParam.objects.order_by("parameter_id"),
    )
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

    # Collezioni già prefetchate e ordinate lato DB
    return render(
        request,
        "submissions/detail.html",
        {
            "sub": sub,
            "sub_answers": list(sub.answers.all()),
            "sub_mots": list(sub.answer_motivations.all()),
            "sub_examples": list(sub.examples.all()),
            "sub_params": list(sub.params.all()),
        },
    )
