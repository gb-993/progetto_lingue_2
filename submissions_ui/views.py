from __future__ import annotations

from typing import Any

from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Subquery, IntegerField, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.db.models import Count
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


def _is_admin(user: Any) -> bool:
    """Return whether the provided user has administrator privileges.

    Args:
        user: User-like object attached to the current request.

    Returns:
        ``True`` when the user is authenticated and staff or role ``admin``;
        otherwise ``False``.
    """
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


def _safe_next_url(request: HttpRequest, fallback_name: str = "submissions_list") -> str:
    """Resolve a safe redirect target from POST/referrer with fallback.

    Args:
        request: Current HTTP request.
        fallback_name: URL name used when candidate target is missing/unsafe.

    Returns:
        A safe local URL string.
    """
    candidate = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse(fallback_name)
    return candidate if url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()) else reverse(fallback_name)


@login_required
@user_passes_test(_is_admin)
def submission_create_for_language(request: HttpRequest, language_id: str) -> HttpResponse:
    """Create a submission snapshot for one language.

    Args:
        request: Current authenticated admin request.
        language_id: Language identifier from URL.

    Returns:
        Confirmation page on GET, or redirect response after creation on POST.
    """
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

@login_required
@user_passes_test(_is_admin)
def submissions_list(request: HttpRequest) -> HttpResponse:
    """Render submissions grouped by backup timestamp or folder content.

    When ``timestamp`` is provided, the view shows submissions inside a single
    backup folder with sorting and pagination. Otherwise, it shows backup
    folders grouped by submission timestamp.

    Args:
        request: Current authenticated admin request.

    Returns:
        Rendered submissions list page.
    """
    selected_ts = request.GET.get("timestamp")
    q = (request.GET.get("q") or "").strip()

    if selected_ts:
        # --- VISTA CONTENUTO (Dentro la cartella) ---
        qs = Submission.objects.filter(submitted_at=selected_ts).select_related("language", "submitted_by")

        if q:
            qs = qs.filter(Q(language__id__icontains=q) | Q(language__name_full__icontains=q))

        # --- LOGICA ORDINAMENTO (NUOVA) ---
        sort = request.GET.get("sort", "name")  # default per nome
        direction = request.GET.get("dir", "asc")

        # Mappa i parametri URL ai campi del database (tramite la relazione language__)
        order_map = {
            "id": "language__id",
            "name": "language__name_full",
            "family": "language__family",  # Se vuoi ordinare anche per famiglia
        }

        # Recupera il campo o usa il default
        db_sort = order_map.get(sort, "language__name_full")

        # Gestione direzione
        if direction == "desc":
            db_sort = f"-{db_sort}"

        # Applica ordinamento
        qs = qs.order_by(db_sort)

        # Helper per generare i link mantenendo il timestamp e la ricerca
        def make_sort_url(field: str) -> str:
            """Build a sort URL preserving active querystring parameters.

            Args:
                field: Logical sort field key.

            Returns:
                Querystring URL with toggled sort direction.
            """
            params = request.GET.copy()
            params["sort"] = field
            # Inverte la direzione se sto cliccando sulla colonna già attiva
            params["dir"] = "desc" if sort == field and direction == "asc" else "asc"
            return f"?{params.urlencode()}"

        sort_urls = {
            "id": make_sort_url("id"),
            "name": make_sort_url("name"),
            # "family": make_sort_url("family"),
        }

        # Paginazione
        paginator = Paginator(qs, 200)
        page = paginator.get_page(request.GET.get("page"))

        return render(request, "submissions/list.html", {
            "page": page,
            "q": q,
            "is_folder_view": False,
            "selected_ts": selected_ts,
            # Passiamo i dati per l'ordinamento al template
            "sort": sort,
            "dir": direction,
            "sort_urls": sort_urls,
        })

    else:
        # --- VISTA CARTELLE (Invariata) ---
        # ... (codice precedente per le cartelle) ...
        groups = Submission.objects.values('submitted_at', 'note', 'submitted_by__email') \
            .annotate(lang_count=Count('id')) \
            .order_by('-submitted_at')
        if q:
            groups = groups.filter(Q(note__icontains=q) | Q(submitted_at__icontains=q))

        paginator = Paginator(groups, 20)
        page = paginator.get_page(request.GET.get("page"))

        return render(request, "submissions/list.html", {
            "page": page,
            "q": q,
            "is_folder_view": True
        })



@login_required
@user_passes_test(_is_admin)
def submission_detail(request: HttpRequest, submission_id: int) -> HttpResponse:
    """Render the details of one submission with ordered related data.

    The view prefetches answers, params, motivations, and examples, and
    computes a motivation text aggregation per answer row.

    Args:
        request: Current authenticated admin request.
        submission_id: Submission primary key.

    Returns:
        Rendered submission detail page.
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




@login_required
@user_passes_test(_is_admin)
def submission_create_all_languages(request: HttpRequest) -> HttpResponse:
    """Create one synchronized backup submission for every language.

    On POST, submissions are generated in a single transaction and forced to
    share the same ``submitted_at`` timestamp.

    Args:
        request: Current authenticated admin request.

    Returns:
        Confirmation page on GET, or redirect to list after backup creation.
    """
    if request.method == "POST":
        note = request.POST.get("note") or "Bulk creation"
        languages = Language.objects.all()

        fixed_time = timezone.now().replace(microsecond=0)

        with transaction.atomic():
            for lang in languages:
                # Creiamo la submission normalmente
                res = create_language_submission(lang, request.user, note=note)
                # 2. FORZIAMO la data identica per tutti
                res.submission.submitted_at = fixed_time
                res.submission.save()

        messages.success(request, _("Backup created successfully."))
        return redirect("submissions_list")

    return render(request, "submissions/confirm_create_all.html")


@login_required
@user_passes_test(_is_admin)
def submission_delete_backup(request: HttpRequest) -> HttpResponse:
    """Delete all submissions belonging to a specific backup timestamp.

    Args:
        request: Current authenticated admin request.

    Returns:
        Redirect response to the submissions list.
    """
    if request.method == "POST":
        # Recuperiamo la data dal form
        timestamp_str = request.POST.get("timestamp")

        if timestamp_str:
            # Cancelliamo tutte le submission che hanno ESATTAMENTE quella data
            # Django gestisce la conversione stringa -> datetime automaticamente nel filtro
            deleted_count, _ = Submission.objects.filter(submitted_at=timestamp_str).delete()

            if deleted_count > 0:
                messages.success(request, f"Backup from {timestamp_str} deleted. ({deleted_count} items removed).")
            else:
                messages.warning(request, "No backup found with this date.")

    return redirect("submissions_list")