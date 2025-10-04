# languages_ui/views.py  — versione pulita/robusta

from __future__ import annotations

from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator

from core.models import (
    Language,
    ParameterDef,
    Question,
    Answer,
    Example,
    Motivation,
    AnswerMotivation,
    QuestionAllowedMotivation,
    LanguageParameter,          # consolidato (+/-/None)
)

# Valori DAG (+/-/0): il modello potrebbe non esistere in ambienti vecchi
try:
    from core.models import LanguageParameterEval   # noqa
    HAS_EVAL = True
except Exception:
    LanguageParameterEval = None  # type: ignore
    HAS_EVAL = False  # non usato ma utile per futuri rami

# Servizi
from core.services.dag_eval import run_dag_for_language
from core.services.dag_debug import diagnostics_for_language


# -----------------------
# Helpers & guardrail
# -----------------------
def _is_admin(user) -> bool:
    """Ruolo amministrativo o staff/superuser."""
    return (getattr(user, "role", "") == "admin") or bool(user.is_staff) or bool(user.is_superuser)


def _check_language_access(user, lang: Language) -> bool:
    """Admin sempre sì; altrimenti la lingua deve essere assegnata via FK o M2M."""
    if _is_admin(user):
        return True
    if getattr(lang, "assigned_user_id", None) == user.id:
        return True
    try:
        if lang.users.filter(pk=user.pk).exists():
            return True
    except Exception:
        pass
    return False


# -----------------------
# List / CRUD lingua
# -----------------------
@login_required
def language_list(request):
    q = (request.GET.get("q") or "").strip()
    user = request.user
    is_admin = _is_admin(user)

    qs = Language.objects.select_related("assigned_user").order_by("position")

    # 🔒 Solo proprie lingue se non admin
    if not is_admin:
        qs = qs.filter(Q(assigned_user=user) | Q(users=user))

    # 🔎 Ricerca (email assegnata visibile solo ad admin)
    if q:
        filt = (
            Q(id__icontains=q)
            | Q(name_full__icontains=q)
            | Q(isocode__icontains=q)
            | Q(glottocode__icontains=q)
            | Q(grp__icontains=q)
            | Q(informant__icontains=q)
            | Q(supervisor__icontains=q)
        )
        if is_admin:
            filt |= Q(assigned_user__email__icontains=q)
        qs = qs.filter(filt)

    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    ctx = {
        "languages": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "is_admin": is_admin,
    }
    return render(request, "languages/list.html", ctx)


@login_required
@require_http_methods(["GET", "POST"])
def language_add(request):
    from .forms import LanguageForm  # import locale per evitare cicli
    if request.method == "POST":
        form = LanguageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Language created."))
            return redirect("language_list")
    else:
        form = LanguageForm()
    return render(request, "languages/add.html", {"page_title": "Add language", "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def language_edit(request, lang_id):
    from .forms import LanguageForm  # import locale per evitare cicli
    lang = get_object_or_404(Language, pk=lang_id)
    if request.method == "POST":
        form = LanguageForm(request.POST, instance=lang)
        if form.is_valid():
            form.save()
            messages.success(request, _("Language updated."))
            return redirect("language_list")
    else:
        form = LanguageForm(instance=lang)
    return render(request, "languages/edit.html", {"page_title": "Edit language", "form": form, "language": lang})


# -----------------------
# Pagina data/compilazione
# -----------------------
@login_required
def language_data(request, lang_id):
    user = request.user
    lang = get_object_or_404(Language, pk=lang_id)

    if not _check_language_access(user, lang):
        messages.error(request, _("You don't have access to this language."))
        return redirect("language_list")

    # Parametri attivi + domande + allowed motivations (ordinati, prefetch)
    parameters = (
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=(
                    Question.objects.order_by("id")
                    .prefetch_related(
                        Prefetch(
                            "allowed_motivation_links",
                            queryset=(
                                QuestionAllowedMotivation.objects
                                .select_related("motivation")
                                .order_by("position", "id")
                            ),
                            to_attr="allowed_motivs_through",
                        )
                    )
                ),
            )
        )
    )

    # Risposte già presenti per la lingua
    answers_qs = (
        Answer.objects.filter(language=lang)
        .select_related("question")
        .prefetch_related("answer_motivations__motivation", "examples")
    )
    by_qid = {a.question_id: a for a in answers_qs}

    # Costruzione “view model” per il template
    for p in parameters:
        total = 0
        answered = 0
        for q in p.questions.all():
            total += 1

            # Motivazioni ammesse (tramite ponte)
            q.allowed_motivations_list = [thr.motivation for thr in getattr(q, "allowed_motivs_through", [])]

            a = by_qid.get(q.id)
            if a:
                ans_ns = SimpleNamespace(
                    response_text=a.response_text,
                    comments=a.comments or "",
                    motivation_ids=[am.motivation_id for am in a.answer_motivations.all()],
                    examples=list(a.examples.all()),
                    answer_id=a.id,
                )
                if a.response_text in ("yes", "no"):
                    answered += 1
            else:
                ans_ns = SimpleNamespace(
                    response_text="",  # default
                    comments="",
                    motivation_ids=[],
                    examples=[],
                    answer_id=None,
                )
            q.ans = ans_ns

        if total == 0:
            p.status = "ok"
        elif answered == 0:
            p.status = "missing"
        elif answered < total:
            p.status = "warn"
        else:
            p.status = "ok"

    ctx = {"language": lang, "parameters": parameters}
    return render(request, "languages/data.html", ctx)


# -----------------------
# Salvataggio risposte
# -----------------------
@login_required
@require_http_methods(["POST"])
def answer_save(request, lang_id, question_id):
    """
    Salva Answer (yes/no), comments e motivazioni multiple.
    - Motivazioni visibili lato client solo se NO, ma qui validiamo lato server.
    - Le motivazioni devono essere tra le allowed della domanda.
    - 'Motivazione1' (se presente) è esclusiva.
    """
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _("You don't have access to this language."))
        return redirect("language_list")

    question = get_object_or_404(Question, pk=question_id)

    response_text = (request.POST.get("response_text") or "").strip().lower()
    if response_text not in ("yes", "no"):
        messages.error(request, _("Invalid answer value."))
        return redirect("language_data", lang_id=lang.id)

    comments = (request.POST.get("comments") or "").strip()

    # Motivazioni inviate
    try:
        motivation_ids = [int(x) for x in request.POST.getlist("motivation_ids")]
    except ValueError:
        motivation_ids = []

    # Ammissibilità per questa domanda
    allowed_ids = set(
        QuestionAllowedMotivation.objects.filter(question=question).values_list("motivation_id", flat=True)
    )

    # Se YES, nessuna motivazione
    if response_text == "yes":
        motivation_ids = []
    else:
        # Filtra al sottoinsieme ammesso
        motivation_ids = [mid for mid in motivation_ids if mid in allowed_ids]

        # Esclusiva 'Motivazione1'
        mot1 = Motivation.objects.filter(label="Motivazione1").only("id").first()
        if mot1 and mot1.id in motivation_ids:
            motivation_ids = [mot1.id]

    # Upsert Answer
    answer, _created = Answer.objects.get_or_create(
        language=lang,
        question=question,
        defaults={"response_text": response_text, "comments": comments},
    )
    answer.response_text = response_text
    answer.comments = comments
    answer.save()

    # Sync motivazioni (delta)
    current_ids = set(
        AnswerMotivation.objects.filter(answer=answer).values_list("motivation_id", flat=True)
    )
    target_ids = set(motivation_ids)

    to_add = target_ids - current_ids
    to_del = current_ids - target_ids

    if to_add:
        AnswerMotivation.objects.bulk_create(
            [AnswerMotivation(answer=answer, motivation_id=mid) for mid in to_add],
            ignore_conflicts=True,
        )
    if to_del:
        AnswerMotivation.objects.filter(answer=answer, motivation_id__in=to_del).delete()

    # Aggiorna Examples (pattern: ex_<id>_<field>)
    for key, val in request.POST.items():
        if not key.startswith("ex_"):
            continue
        try:
            _ex, ex_id, field = key.split("_", 2)
            ex_id = int(ex_id)
        except ValueError:
            continue
        if field not in {"textarea", "transliteration", "gloss", "translation", "reference"}:
            continue
        Example.objects.filter(id=ex_id, answer=answer).update(**{field: val})

    messages.success(request, _("Answer saved."))
    return redirect("language_data", lang_id=lang.id)


# -----------------------
# Export / approvazioni (placeholder)
# -----------------------
@login_required
def language_export(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _("You don't have access to this language."))
        return redirect("language_list")
    messages.info(request, _("Export is not implemented yet."))
    return redirect("language_data", lang_id=lang.id)


@login_required
def language_save_instructions(request, lang_id):
    if not _is_admin(request.user):
        messages.error(request, _("You are not allowed to perform this action."))
        return redirect("language_list")
    messages.info(request, _("Instructions are not supported yet (no model to store them)."))
    return redirect("language_data", lang_id=lang_id)


@login_required
def language_approve(request, lang_id):
    if not _is_admin(request.user):
        messages.error(request, _("You are not allowed to perform this action."))
        return redirect("language_list")
    messages.info(request, _("Approval flow not implemented yet."))
    return redirect("language_data", lang_id=lang_id)


@login_required
def language_reopen(request, lang_id):
    if not _is_admin(request.user):
        messages.error(request, _("You are not allowed to perform this action."))
        return redirect("language_list")
    messages.info(request, _("Reopen flow not implemented yet."))
    return redirect("language_data", lang_id=lang_id)


# -----------------------
# Pagina DEBUG con diagnostica e run DAG
# -----------------------
@login_required
def language_debug(request, lang_id: str):
    """
    Debug per una lingua:
      - Per ogni parametro attivo (in ordine di position)
      - Mostra: ID domande, risposte yes/no, value_orig (+/-), value_eval (+/-/0),
        warning init/final, condizione raw e pretty, e l'esito della condizione.
    """
    user = request.user
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(user, lang):
        # 404 per non rivelare l'esistenza della lingua
        get_object_or_404(Language, pk="__deny__")

    # Parametri attivi + domande
    params = (
        ParameterDef.objects
        .filter(is_active=True)
        .order_by("position", "id")
        .prefetch_related(Prefetch("questions", queryset=Question.objects.order_by("id")))
    )

    # Risposte per la lingua
    answers = (
        Answer.objects
        .filter(language=lang)
        .select_related("question")
        .order_by("question__parameter__position", "question_id")
    )
    answers_by_qid = {a.question_id: a for a in answers}

    # initial/final + warnings
    lps = (
        LanguageParameter.objects
        .filter(language=lang)
        .select_related("parameter", "eval")
    )

    init_by_pid, warni_by_pid = {}, {}
    final_by_pid, warnf_by_pid = {}, {}

    for lp in lps:
        pid = lp.parameter_id
        init_by_pid[pid] = (lp.value_orig or "")
        warni_by_pid[pid] = bool(lp.warning_orig)
        if getattr(lp, "eval", None):
            final_by_pid[pid] = (lp.eval.value_eval or "")
            warnf_by_pid[pid] = bool(lp.eval.warning_eval)
        else:
            final_by_pid[pid] = ""
            warnf_by_pid[pid] = False

    # Righe per tabella principale
    rows = []
    for p in params:
        q_ids, q_ans = [], []
        for q in p.questions.all():
            q_ids.append(q.id)
            a = answers_by_qid.get(q.id)
            q_ans.append(a.response_text.upper() if (a and a.response_text in ("yes", "no")) else "")
        rows.append({
            "position": p.position,
            "param_id": p.id,
            "name": p.name or "",
            "questions": q_ids,
            "answers": q_ans,
            "initial":  (init_by_pid.get(p.id, "") or ""),
            "final":    (final_by_pid.get(p.id, "") or ""),
            "warn_init": bool(warni_by_pid.get(p.id, False)),
            "warn_final": bool(warnf_by_pid.get(p.id, False)),
            "cond": (p.implicational_condition or ""),
        })

    # Diagnostica parser/condizioni (pretty + TRUE/FALSE)
    diag_rows = diagnostics_for_language(lang)

    ctx = {"language": lang, "rows": rows, "diag_rows": diag_rows, "is_admin": _is_admin(user)}
    return render(request, "languages/debug_parameters.html", ctx)


# -----------------------
# Azione: esecuzione DAG
# -----------------------
@login_required
@require_POST
def language_run_dag(request, lang_id: str):
    if not _is_admin(request.user):
        messages.error(request, _("You are not allowed to run the DAG."))
        return redirect("language_debug", lang_id=lang_id)

    try:
        report = run_dag_for_language(lang_id)
        msg = _(
            "DAG completed: processed %(p)d, forced to zero %(fz)d, missing orig %(mo)d, warnings propagated %(wp)d."
        ) % {
            "p": len(report.processed or []),
            "fz": len(report.forced_zero or []),
            "mo": len(report.missing_orig or []),
            "wp": len(report.warnings_propagated or []),
        }
        if report.missing_orig:
            msg += " Missing: " + ", ".join(report.missing_orig[:8]) + ("…" if len(report.missing_orig) > 8 else "")
        if report.parse_errors:
            msg += " ParseErrors: " + ", ".join(f"{pid}" for (pid, _, _) in report.parse_errors[:6]) + ("…" if len(report.parse_errors) > 6 else "")
        messages.success(request, msg)
    except Exception as e:
        messages.error(request, _("DAG failed: %(err)s") % {"err": str(e)})

    return redirect("language_debug", lang_id=lang_id)
