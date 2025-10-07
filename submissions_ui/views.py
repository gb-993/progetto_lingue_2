# submissions_ui/views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.utils.translation import gettext as _
from core.models import Language, Submission
from .services import create_language_submission
from django.urls import reverse

def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))

@login_required
@user_passes_test(_is_admin)
def submission_create_for_language(request, language_id):
    lang = get_object_or_404(Language, pk=language_id)

    if request.method == "POST":
        res = create_language_submission(
            lang,
            request.user,
            note=request.POST.get("note") or ""
        )

        from django.contrib import messages
        messages.success(
            request,
            _("Submission creata per %(lang)s alle %(ts)s (pruned=%(p)d)") % {
                "lang": lang.id,
                "ts": res.submission.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                "p": res.pruned_count,
            },
        )

        # torna alla pagina di provenienza o, se mancante, alla lista submissions
        next_url = (
            request.POST.get("next")
            or request.META.get("HTTP_REFERER")
            or reverse("submissions_list")
        )
        return redirect(next_url)

    # GET: pagina di conferma minimale (in pratica non usata perché invii POST)
    return render(request, "submissions/confirm_create.html", {"language": lang})


@login_required
@user_passes_test(_is_admin)
def submissions_list(request):
    qs = Submission.objects.select_related("language", "submitted_by").order_by("-submitted_at", "-id")
    # filtri semplici
    language_id = (request.GET.get("language") or "").strip()
    if language_id:
        qs = qs.filter(language_id=language_id)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "submissions/list.html", {"page": page, "language_id": language_id})

@login_required
@user_passes_test(_is_admin)
def submission_detail(request, submission_id):
    sub = get_object_or_404(
        Submission.objects.select_related("language", "submitted_by"),
        pk=submission_id
    )
    # Prefetch risorse collegate (attenzione: pagina solo lettura)
    sub_answers = sub.answers.all().order_by("question_code")
    sub_mots = sub.answer_motivations.all()
    sub_examples = sub.examples.all()
    sub_params = sub.params.all().order_by("parameter_id")
    return render(request, "submissions/detail.html", {
        "sub": sub,
        "sub_answers": sub_answers,
        "sub_mots": sub_mots,
        "sub_examples": sub_examples,
        "sub_params": sub_params,
    })
