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
from django.db import transaction


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

def _language_status_summary(lang: Language):
    """
    Conteggi per stato e 'overall' derivato:
    - 'approved' se tutte le answers esistenti sono approved
    - 'waiting_for_approval' se tutte le answers esistenti sono waiting
    - 'rejected' se esiste almeno una rejected e nessuna waiting
    - 'pending' altrimenti (misti, presenti pending o nessuna answer)
    """
    qs = Answer.objects.filter(language=lang).values_list("status", flat=True)
    counts = {"pending": 0, "waiting_for_approval": 0, "approved": 0, "rejected": 0}
    total = 0
    for s in qs:
        counts[s] = counts.get(s, 0) + 1
        total += 1

    if total == 0:
        overall = "pending"
    elif counts["approved"] == total:
        overall = "approved"
    elif counts["waiting_for_approval"] == total:
        overall = "waiting_for_approval"
    elif counts["rejected"] > 0 and counts["waiting_for_approval"] == 0:
        overall = "rejected"
    else:
        overall = "pending"

    return {"counts": counts, "total": total, "overall": overall}


def _missing_answered_question_ids(lang: Language):
    """
    Ritorna gli id delle domande attive che NON hanno una Answer yes/no per questa lingua.
    Serve a impedire 'submit' con risposte mancanti.
    """
    active_qids = set(
        Question.objects.filter(parameter__is_active=True).values_list("id", flat=True)
    )
    answered_qids = set(
        Answer.objects.filter(
            language=lang,
            question_id__in=active_qids,
            response_text__in=["yes", "no"]
        ).values_list("question_id", flat=True)
    )
    return sorted(active_qids - answered_qids)


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
    is_admin = _is_admin(user)  # <-- aggiungi

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
    # ---- Aggiunta: stato complessivo per la UI ----
    status_summary = _language_status_summary(lang)
    all_ok = all(getattr(p, "status", "missing") == "ok" for p in parameters)
    
    ctx = {"language": lang, "parameters": parameters, "is_admin": is_admin, "lang_status": SimpleNamespace(**status_summary),"all_answered": all_ok,}
    return render(request, "languages/data.html", ctx)


# -----------------------
# Salvataggio risposte
# -----------------------
@login_required
@require_http_methods(["POST"])
def answer_save(request, lang_id, question_id):
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

    # Rispetta 'modifiable' per gli utenti; gli ADMIN possono bypassare
    answer = Answer.objects.filter(language=lang, question=question).first()
    if answer and not answer.modifiable and not _is_admin(request.user):
        messages.error(request, _("This answer is locked (waiting/approved)."))
        return redirect("language_data", lang_id=lang.id)

    # Motivazioni
    try:
        motivation_ids = [int(x) for x in request.POST.getlist("motivation_ids")]
    except ValueError:
        motivation_ids = []

    allowed_ids = set(
        QuestionAllowedMotivation.objects.filter(question=question)
        .values_list("motivation_id", flat=True)
    )

    if response_text == "yes":
        motivation_ids = []
    else:
        motivation_ids = [mid for mid in motivation_ids if mid in allowed_ids]
        mot1 = Motivation.objects.filter(label="Motivazione1").only("id").first()
        if mot1 and mot1.id in motivation_ids:
            motivation_ids = [mot1.id]

    if answer is None:
        answer = Answer(language=lang, question=question, response_text=response_text, comments=comments)
    else:
        answer.response_text = response_text
        answer.comments = comments
    answer.save()

    # Sync motivazioni
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

    # Examples
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


@login_required
@require_POST
def answers_bulk_save(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _("You don't have access to this language."))
        return redirect("language_list")

    questions = (
        Question.objects
        .filter(parameter__is_active=True)
        .select_related("parameter")
        .order_by("parameter__position", "id")
    )

    allowed_by_qid = {
        q.id: set(QuestionAllowedMotivation.objects.filter(question=q).values_list("motivation_id", flat=True))
        for q in questions
    }

    saved, skipped_locked = 0, 0
    with transaction.atomic():
        answers_by_q = {
            a.question_id: a
            for a in Answer.objects.select_for_update().filter(language=lang, question__in=questions)
        }

        for q in questions:
            rt = (request.POST.get(f"response_text_{q.id}") or "").strip().lower()
            cm = (request.POST.get(f"comments_{q.id}") or "").strip()
            if rt not in ("yes", "no"):
                continue

            a = answers_by_q.get(q.id)
            # Utente non-admin non può modificare answer locked
            if a and not a.modifiable and not _is_admin(request.user):
                skipped_locked += 1
                continue

            try:
                mot_ids = [int(x) for x in request.POST.getlist(f"motivation_ids_{q.id}")]
            except ValueError:
                mot_ids = []

            if rt == "yes":
                mot_ids = []
            else:
                allowed = allowed_by_qid.get(q.id, set())
                mot_ids = [mid for mid in mot_ids if mid in allowed]
                mot1 = Motivation.objects.filter(label="Motivazione1").only("id").first()
                if mot1 and mot1.id in mot_ids:
                    mot_ids = [mot1.id]

            if a is None:
                a = Answer(language=lang, question=q, response_text=rt, comments=cm)
                a.save()
                answers_by_q[q.id] = a
            else:
                a.response_text = rt
                a.comments = cm
                a.save()

            # Sync motivazioni
            cur = set(AnswerMotivation.objects.filter(answer=a).values_list("motivation_id", flat=True))
            tgt = set(mot_ids)
            to_add = tgt - cur
            to_del = cur - tgt
            if to_add:
                AnswerMotivation.objects.bulk_create(
                    [AnswerMotivation(answer=a, motivation_id=mid) for mid in to_add],
                    ignore_conflicts=True,
                )
            if to_del:
                AnswerMotivation.objects.filter(answer=a, motivation_id__in=to_del).delete()

            # Examples
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
                Example.objects.filter(id=ex_id, answer=a).update(**{field: val})

            saved += 1

    if skipped_locked:
        messages.warning(request, _(f"Saved {saved} answers. Skipped {skipped_locked} locked answers (waiting/approved)."))
    else:
        messages.success(request, _(f"Saved {saved} answers (others left unchanged)."))

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
    
    # SOLO admin
    if not _is_admin(user):
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


@login_required
@require_POST
def language_submit(request, lang_id):
    """USER: pending|rejected -> waiting (lock) solo se tutte le domande attive hanno risposta."""
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _("You don't have access to this language."))
        return redirect("language_list")

    # Precondizione: tutte le domande attive devono avere yes/no
    missing = _missing_answered_question_ids(lang)
    if missing:
        first = ", ".join(missing[:8]) + ("…" if len(missing) > 8 else "")
        messages.error(request, _("You must answer all active questions before submitting. Missing: ") + first)
        return redirect("language_data", lang_id=lang.id)

    with transaction.atomic():
        answers = list(Answer.objects.select_for_update().filter(language=lang))
        changed = 0
        for a in answers:
            if a.status in ("pending", "rejected"):
                a.status = "waiting_for_approval"
                a.modifiable = False
                a.save(update_fields=["status", "modifiable"])
                changed += 1

    if changed == 0:
        messages.info(request, _("Nothing to submit."))
    else:
        messages.success(request, _(f"Submitted {changed} answers for approval."))
    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_approve(request, lang_id):
    """ADMIN: waiting -> approved + run DAG (idempotente). Richiede tutte le risposte waiting (o già approved)."""
    if not _is_admin(request.user):
        messages.error(request, _("You are not allowed to perform this action."))
        return redirect("language_list")

    lang = get_object_or_404(Language, pk=lang_id)

    # Verifica che non manchino risposte attive
    missing = _missing_answered_question_ids(lang)
    if missing:
        first = ", ".join(missing[:8]) + ("…" if len(missing) > 8 else "")
        messages.error(request, _("Cannot approve: missing answers: ") + first)
        return redirect("language_data", lang_id=lang.id)

    with transaction.atomic():
        answers = list(Answer.objects.select_for_update().filter(language=lang))
        if not answers:
            messages.error(request, _("No answers to approve."))
            return redirect("language_data", lang_id=lang.id)

        invalid = [a for a in answers if a.status not in ("waiting_for_approval", "approved")]
        if invalid:
            messages.error(request, _("All answers must be in 'waiting' to approve."))
            return redirect("language_data", lang_id=lang.id)

        changed = 0
        for a in answers:
            if a.status == "waiting_for_approval":
                a.status = "approved"
                a.modifiable = False
                a.save(update_fields=["status", "modifiable"])
                changed += 1

    # Esegui DAG (idempotente). Se fallisce, lo segnaliamo ma non rollbackiamo l'approvazione.
    try:
        _ = run_dag_for_language(lang_id)
        messages.success(request, _(f"Approved {changed} answers and ran DAG."))
    except Exception as e:
        messages.warning(request, _("Approved, but DAG failed: %(err)s") % {"err": str(e)})

    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_reject(request, lang_id):
    """ADMIN: waiting -> rejected (riapre editing per USER)."""
    if not _is_admin(request.user):
        messages.error(request, _("You are not allowed to perform this action."))
        return redirect("language_list")

    lang = get_object_or_404(Language, pk=lang_id)
    with transaction.atomic():
        answers = list(Answer.objects.select_for_update().filter(language=lang))
        if not answers:
            messages.error(request, _("No answers to reject."))
            return redirect("language_data", lang_id=lang.id)

        invalid = [a for a in answers if a.status not in ("waiting_for_approval", "rejected")]
        if invalid:
            messages.error(request, _("All answers must be in 'waiting' to reject."))
            return redirect("language_data", lang_id=lang.id)

        changed = 0
        for a in answers:
            if a.status == "waiting_for_approval":
                a.status = "rejected"
                a.modifiable = True
                a.save(update_fields=["status", "modifiable"])
                changed += 1

    messages.success(request, _(f"Rejected {changed} answers. Users can edit again."))
    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_reopen(request, lang_id):
    """USER: rejected -> pending (sblocco dopo banner)."""
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _("You don't have access to this language."))
        return redirect("language_list")

    with transaction.atomic():
        answers = list(Answer.objects.select_for_update().filter(language=lang, status="rejected"))
        changed = 0
        for a in answers:
            a.status = "pending"
            a.modifiable = True
            a.save(update_fields=["status", "modifiable"])
            changed += 1

    if changed == 0:
        messages.info(request, _("Nothing to reopen."))
    else:
        messages.success(request, _(f"Reopened {changed} answers. You can edit again."))
    return redirect("language_data", lang_id=lang.id)
