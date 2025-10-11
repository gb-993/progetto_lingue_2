# languages_ui/views.py — versione pulita/robusta

from __future__ import annotations

from types import SimpleNamespace
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _t
from django.views.decorators.http import require_http_methods, require_POST
from django.http import HttpResponse, Http404
from django.utils.timezone import now
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from core.models import (
    Language,
    ParameterDef,
    Question,
    Answer,
    Example,
    Motivation,
    AnswerMotivation,
    QuestionAllowedMotivation,
    LanguageParameter,          
)
# Valori DAG (+/-/0): il modello potrebbe non esistere in ambienti vecchi
try:
    from core.models import LanguageParameterEval  
    HAS_EVAL = True
except Exception:
    LanguageParameterEval = None 
    HAS_EVAL = False  

# Se gli status sono definiti nel modello:
try:
    from core.models import AnswerStatus  # PENDING/WAITING/APPROVED/REJECTED
except Exception:
    # (evita crash se l'enum non è disponibile)
    class AnswerStatus:
        PENDING = "pending"
        WAITING = "waiting_for_approval"
        APPROVED = "approved"
        REJECTED = "rejected"

from core.models import LanguageReview  # log decisioni approve/reject

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


def _language_status_summary(lang: Language):
    """
    Conteggi per stato e 'overall' derivato (compat):
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


def _language_overall_status(lang: Language) -> dict:
    """
    Calcola lo stato 'overall' in base agli status delle Answer.
    Priorità: WAITING > APPROVED > REJECTED > PENDING.
    """
    qs = Answer.objects.filter(language=lang).values_list("status", flat=True)
    seen = set(qs)

    if AnswerStatus.WAITING in seen:
        overall = AnswerStatus.WAITING
    elif AnswerStatus.APPROVED in seen:
        overall = AnswerStatus.APPROVED
    elif AnswerStatus.REJECTED in seen:
        overall = AnswerStatus.REJECTED
    else:
        overall = AnswerStatus.PENDING

    # conteggi elementari (non usati molto, ma utili)
    counts = {
        "pending":   sum(1 for s in qs if s == AnswerStatus.PENDING),
        "waiting":   sum(1 for s in qs if s == AnswerStatus.WAITING),
        "approved":  sum(1 for s in qs if s == AnswerStatus.APPROVED),
        "rejected":  sum(1 for s in qs if s == AnswerStatus.REJECTED),
    }
    return {"overall": overall, "counts": counts}


def _all_questions_answered(language: Language) -> bool:
    """
    True se TUTTE le domande attive hanno una Answer yes/no per questa lingua.
    """
    active_qids = set(
        Question.objects.filter(parameter__is_active=True).values_list("id", flat=True)
    )
    if not active_qids:
        return False  # se non hai domande, non consento approvazione
    answered_qids = set(
        Answer.objects.filter(
            language=language,
            question_id__in=active_qids,
            response_text__in=["yes", "no"],
        ).values_list("question_id", flat=True)
    )
    return active_qids.issubset(answered_qids)

# --- Helper riusabile: logica di salvataggio singola domanda (senza redirect/messages) ---
from django.http import QueryDict

def _answer_save_core(*, user, lang, question, post_dict):
    # 1) Normalizza input
    response_text = (post_dict.get("response_text") or "").strip().lower()
    if response_text not in ("yes", "no"):
        return False, "invalid"  # ignora/errore soft

    comments = (post_dict.get("comments") or "").strip()

    # 2) Carica/lock Answer
    answer = (
        Answer.objects.select_for_update()
        .filter(language=lang, question=question)
        .first()
    )

    # Rispetta 'modifiable' per gli utenti; ADMIN bypassa
    if answer and not answer.modifiable and not _is_admin(user):
        return False, "locked"

    # 3) Motivazioni: leggi e filtra
    try:
        motivation_ids = [int(x) for x in post_dict.getlist("motivation_ids")]
    except ValueError:
        motivation_ids = []

    allowed_ids = set(
        QuestionAllowedMotivation.objects.filter(question=question)
        .values_list("motivation_id", flat=True)
    )

    # Esclusività "Motivazione1" via codice stabile
    mot1 = Motivation.objects.filter(code="MOT1").only("id").first()

    if response_text == "yes":
        target_ids = set()  # YES => niente motivazioni
    else:
        filtered = [mid for mid in motivation_ids if mid in allowed_ids]
        if mot1 and (mot1.id in filtered):
            target_ids = {mot1.id}
        else:
            target_ids = set(filtered)

    # 4) Crea/aggiorna Answer
    if answer is None:
        answer = Answer(language=lang, question=question)
    answer.response_text = response_text
    answer.comments = comments
    answer.save()

    # 5) Sync motivazioni
    current_ids = set(
        AnswerMotivation.objects.filter(answer=answer).values_list("motivation_id", flat=True)
    )
    to_add = target_ids - current_ids
    to_del = current_ids - target_ids

    if to_add:
        AnswerMotivation.objects.bulk_create(
            [AnswerMotivation(answer=answer, motivation_id=mid) for mid in to_add],
            ignore_conflicts=True,
        )
    if to_del:
        AnswerMotivation.objects.filter(answer=answer, motivation_id__in=to_del).delete()

    # 6) Esempi (solo se i campi esistono nel post_dict di quella domanda)
    FIELDS = {"number", "textarea", "transliteration", "gloss", "translation", "reference"}

    # 6.0) Delete esistenti: del_ex_<id> = "1"
    del_ids = []
    for key, val in post_dict.items():
        if key.startswith("del_ex_") and val == "1":
            try:
                del_ids.append(int(key.split("_", 2)[2]))
            except ValueError:
                pass
    if del_ids:
        Example.objects.filter(answer=answer, id__in=del_ids).delete()

    # 6.1) Update esempi esistenti: ex_<ID>_<field>
    for key, val in post_dict.items():
        if not key.startswith("ex_"):
            continue
        try:
            _ex, ex_id, field = key.split("_", 2)
            ex_id = int(ex_id)
        except ValueError:
            continue
        if field not in FIELDS:
            continue
        Example.objects.filter(id=ex_id, answer=answer).update(**{field: val})

    # 6.2) Crea esempi nuovi: newex_<QID>_<UID>_<field>
    prefix = f"newex_{question.id}_"
    buckets = {}
    for key, val in post_dict.items():
        if not key.startswith(prefix):
            continue
        remainder = key[len(prefix):]
        try:
            uid, field = remainder.rsplit("_", 1)
        except ValueError:
            continue
        if field not in FIELDS:
            continue
        buckets.setdefault(uid, {})[field] = (val or "").strip()

    if buckets:
        to_create = []
        for uid, data in buckets.items():
            has_payload = any([
                data.get("textarea"),
                data.get("transliteration"),
                data.get("gloss"),
                data.get("translation"),
                data.get("reference"),
            ])
            num = (data.get("number") or "").strip()
            if not has_payload and not num:
                continue
            to_create.append(Example(
                answer=answer,
                number=num or "1",
                textarea=data.get("textarea", ""),
                transliteration=data.get("transliteration", ""),
                gloss=data.get("gloss", ""),
                translation=data.get("translation", ""),
                reference=data.get("reference", ""),
            ))
        if to_create:
            Example.objects.bulk_create(to_create, ignore_conflicts=True)

    # Regola opzionale: YES richiede almeno 1 esempio -> solo warning (non blocchiamo)
    if answer.response_text == "yes":
        if Example.objects.filter(answer=answer).count() == 0:
            return True, "yes_without_examples"

    return True, "ok"

# -----------------------
# List / CRUD lingua
# -----------------------
@login_required
def language_list(request):
    q = (request.GET.get("q") or "").strip()
    user = request.user
    is_admin = _is_admin(user)

    qs = Language.objects.select_related("assigned_user").order_by("position")

    # Solo proprie lingue se non admin
    if not is_admin:
        qs = qs.filter(Q(assigned_user=user) | Q(users=user))

    # Ricerca (email assegnata visibile solo ad admin)
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
            messages.success(request, _t("Language created."))
            return redirect("language_list")
    else:
        form = LanguageForm()
    return render(request, "languages/add.html", {"page_title": "Add language", "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def language_edit(request, lang_id):
    from .forms import LanguageForm  # import locale del form
    lang = get_object_or_404(Language, pk=lang_id)
    if request.method == "POST":
        # instance=lang per fare update e non creare elemento nuovo
        form = LanguageForm(request.POST, instance=lang)
        if form.is_valid():
            form.save()
            messages.success(request, _t("Language updated."))
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
    is_admin = _is_admin(user)
    lang = get_object_or_404(Language, pk=lang_id)

    if not _check_language_access(user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    # Parametri attivi + domande + allowed motivations
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

    # risposte per lingua
    answers_qs = (
        Answer.objects.filter(language=lang)
        .select_related("question")
        .prefetch_related("answer_motivations__motivation", "examples")
    )
    by_qid = {a.question_id: a for a in answers_qs}

    # View model per template + stato per parametro
    for p in parameters:
        total = 0
        answered = 0
        for q in p.questions.all():
            total += 1
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
                    response_text="",
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

    # all_answered = tutte le domande attive hanno yes/no?
    active_q_total = 0
    active_q_answered = 0
    for p in parameters:
        for q in p.questions.all():
            active_q_total += 1
            if getattr(q, "ans", None) and q.ans.response_text in ("yes", "no"):
                active_q_answered += 1
    all_answered = (active_q_total > 0 and active_q_answered == active_q_total)

    lang_status = _language_overall_status(lang)
    last_reject = LanguageReview.objects.filter(language=lang, decision="reject").order_by("-created_at").first()

    ctx = {
        "language": lang,
        "parameters": parameters,
        "is_admin": is_admin,
        "all_answered": all_answered,
        "lang_status": lang_status,
        "last_reject": last_reject,
    }
    return render(request, "languages/data.html", ctx)

from django.db import transaction
from django.utils.translation import gettext as _t
from django.urls import reverse

# -----------------------
# Salvataggio risposte
# -----------------------

@login_required
@require_http_methods(["POST"])
@transaction.atomic
def answer_save(request, lang_id, question_id):
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    question = get_object_or_404(Question, pk=question_id)

    # 1) Normalizza input
    response_text = (request.POST.get("response_text") or "").strip().lower()
    if response_text not in ("yes", "no"):
        messages.error(request, _t("Invalid answer value."))
        return redirect("language_data", lang_id=lang.id)

    comments = (request.POST.get("comments") or "").strip()

    # 2) Carica/lock Answer (evita race-condition)
    answer = (
        Answer.objects.select_for_update()
        .filter(language=lang, question=question)
        .first()
    )

    # Rispetta 'modifiable' per gli utenti; ADMIN bypassa
    if answer and not answer.modifiable and not _is_admin(request.user):
        messages.error(request, _t("This answer is locked (waiting/approved)."))
        return redirect("language_data", lang_id=lang.id)

    # 3) Motivazioni: leggi e filtra
    try:
        motivation_ids = [int(x) for x in request.POST.getlist("motivation_ids")]
    except ValueError:
        motivation_ids = []

    allowed_ids = set(
        QuestionAllowedMotivation.objects.filter(question=question)
        .values_list("motivation_id", flat=True)
    )

    # Esclusività "Motivazione1" via CODE stabile (modelli hanno 'code' unico)
    mot1 = Motivation.objects.filter(code="MOT1").only("id").first()

    if response_text == "yes":
        target_ids = set()  # YES => niente motivazioni
    else:
        filtered = [mid for mid in motivation_ids if mid in allowed_ids]
        if mot1 and mot1.id in filtered:
            target_ids = {mot1.id}
        else:
            target_ids = set(filtered)

    # 4) Crea/aggiorna Answer
    if answer is None:
        answer = Answer(language=lang, question=question)
    answer.response_text = response_text
    answer.comments = comments
    answer.save()  # vincolo unico già in DB

    # 5) Sync motivazioni (differenziale, dentro la stessa transazione)
    current_ids = set(
        AnswerMotivation.objects.filter(answer=answer).values_list("motivation_id", flat=True)
    )
    to_add = target_ids - current_ids
    to_del = current_ids - target_ids

    if to_add:
        AnswerMotivation.objects.bulk_create(
            [AnswerMotivation(answer=answer, motivation_id=mid) for mid in to_add],
            ignore_conflicts=True,  # sicuro: in DB hai uq answer+motivation
        )
    if to_del:
        AnswerMotivation.objects.filter(answer=answer, motivation_id__in=to_del).delete()

    # 6) Examples: delete, update, create (singola domanda)

    FIELDS = {"number", "textarea", "transliteration", "gloss", "translation", "reference"}

    # 6.0) Delete esistenti: del_ex_<id> = "1"
    del_ids = []
    for key, val in request.POST.items():
        if key.startswith("del_ex_") and val == "1":
            try:
                del_ids.append(int(key.split("_", 2)[2]))
            except ValueError:
                pass
    if del_ids:
        Example.objects.filter(answer=answer, id__in=del_ids).delete()

    # 6.1) Update esempi esistenti: ex_<ID>_<field>
    for key, val in request.POST.items():
        if not key.startswith("ex_"):
            continue
        try:
            _ex, ex_id, field = key.split("_", 2)
            ex_id = int(ex_id)
        except ValueError:
            continue
        if field not in FIELDS:
            continue
        cleaned = (val or "").strip()
        Example.objects.filter(id=ex_id, answer=answer).update(**{field: cleaned})

    # 6.2) Crea esempi nuovi: newex_<QID>_<UID>_<field>
    prefix = f"newex_{question.id}_"
    buckets = {}
    for key, val in request.POST.items():
        if not key.startswith(prefix):
            continue
        remainder = key[len(prefix):]
        try:
            uid, field = remainder.rsplit("_", 1)
        except ValueError:
            continue
        if field not in FIELDS:
            continue
        buckets.setdefault(uid, {})[field] = (val or "").strip()

    if buckets:
        to_create = []
        for uid, data in buckets.items():
            has_payload = any([
                data.get("textarea"),
                data.get("transliteration"),
                data.get("gloss"),
                data.get("translation"),
                data.get("reference"),
            ])
            num = (data.get("number") or "").strip()
            # se non c'è niente, salta
            if not has_payload and not num:
                continue
            to_create.append(Example(
                answer=answer,
                number=num or "1",
                textarea=data.get("textarea", ""),
                transliteration=data.get("transliteration", ""),
                gloss=data.get("gloss", ""),
                translation=data.get("translation", ""),
                reference=data.get("reference", ""),
            ))
        if to_create:
            Example.objects.bulk_create(to_create, ignore_conflicts=True)


    messages.success(request, _t("Answer saved."))
    # Migliore UX: ancora sulla domanda
    return redirect(f"{reverse('language_data', kwargs={'lang_id': lang.id})}#p-{question.id}")



@login_required
@require_POST
def answers_bulk_save(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
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
                # esclusività Motivazione1
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

            # --- Examples: delete, update, create ---------------------------------

            # 0) Delete: del_ex_<id> = "1"
            del_ids = []
            for key, val in request.POST.items():
                if key.startswith("del_ex_") and val == "1":
                    try:
                        del_ids.append(int(key.split("_", 2)[2]))
                    except ValueError:
                        pass
            if del_ids:
                Example.objects.filter(answer=a, id__in=del_ids).delete()

            # 1) Update esempi esistenti: ex_<ID>_<field>
            FIELDS = {"number", "textarea", "transliteration", "gloss", "translation", "reference"}
            for key, val in request.POST.items():
                if not key.startswith("ex_"):
                    continue
                try:
                    _ex, ex_id, field = key.split("_", 2)
                    ex_id = int(ex_id)
                except ValueError:
                    continue
                if field not in FIELDS:
                    continue
                Example.objects.filter(id=ex_id, answer=a).update(**{field: val})

            # 2) Crea esempi nuovi: newex_<QID>_<UID>_<field>
            prefix = f"newex_{q.id}_"
            buckets = {}
            for key, val in request.POST.items():
                if not key.startswith(prefix):
                    continue
                remainder = key[len(prefix):]
                try:
                    uid, field = remainder.rsplit("_", 1)
                except ValueError:
                    continue
                if field not in FIELDS:
                    continue
                buckets.setdefault(uid, {})[field] = val

            if buckets:
                to_create = []
                for uid, data in buckets.items():
                    has_payload = any((
                        (data.get("textarea") or "").strip(),
                        (data.get("transliteration") or "").strip(),
                        (data.get("gloss") or "").strip(),
                        (data.get("translation") or "").strip(),
                        (data.get("reference") or "").strip(),
                    ))
                    num = (data.get("number") or "").strip()
                    if not has_payload and not num:
                        continue
                    to_create.append(Example(
                        answer=a,
                        number=num or "1",
                        textarea=(data.get("textarea") or "").strip(),
                        transliteration=(data.get("transliteration") or "").strip(),
                        gloss=(data.get("gloss") or "").strip(),
                        translation=(data.get("translation") or "").strip(),
                        reference=(data.get("reference") or "").strip(),
                    ))
                if to_create:
                    Example.objects.bulk_create(to_create, ignore_conflicts=True)

            # 3) Validazione “YES richiede almeno 1 esempio”
            if rt == "yes":
                ex_count = Example.objects.filter(answer=a).count()
                if ex_count == 0:
                    # segnale soft: non blocco l'intero bulk, ma notifico
                    request._missing_examples_for_yes = getattr(request, "_missing_examples_for_yes", [])
                    request._missing_examples_for_yes.append(str(q.id))
                    # non annullo il salvataggio: lasciamo la risposta e avvisiamo
            saved += 1

    if skipped_locked:
        messages.warning(request, _t("Some locked answers were skipped."))
    messages.success(request, _t(f"Saved {saved} answers."))

    miss = getattr(request, "_missing_examples_for_yes", [])
    if miss:
        messages.error(
            request,
            _t("Answers set to YES require at least one example. Missing for: %(qs)s") % {
                "qs": ", ".join(miss[:10]) + ("…" if len(miss) > 10 else "")
            }
        )

    return redirect("language_data", lang_id=lang.id)




@login_required
def language_save_instructions(request, lang_id):
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to perform this action."))
        return redirect("language_list")
    messages.info(request, _t("Instructions are not supported yet (no model to store them)."))
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

    params = (
        ParameterDef.objects
        .filter(is_active=True)
        .order_by("position", "id")
        .prefetch_related(Prefetch("questions", queryset=Question.objects.order_by("id")))
    )

    answers = (
        Answer.objects
        .filter(language=lang)
        .select_related("question")
        .order_by("question__parameter__position", "question_id")
    )
    answers_by_qid = {a.question_id: a for a in answers}

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

    diag_rows = diagnostics_for_language(lang)

    ctx = {"language": lang, "rows": rows, "diag_rows": diag_rows, "is_admin": _is_admin(user)}
    return render(request, "languages/debug_parameters.html", ctx)


# -----------------------
# Azione: esecuzione DAG manuale
# -----------------------
@login_required
@require_POST
def language_run_dag(request, lang_id: str):
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to run the DAG."))
        return redirect("language_debug", lang_id=lang_id)

    try:
        report = run_dag_for_language(lang_id)
        msg = _t(
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
        messages.error(request, _t("DAG failed: %(err)s") % {"err": str(e)})

    return redirect("language_debug", lang_id=lang_id)


# -----------------------
# Flusso submit/approve/reject/reopen
# -----------------------
@login_required
@require_POST
def language_submit(request, lang_id):
    """
    USER: submit finale SEMPRE consentita anche con risposte mancanti.
    Blocca l'editing (WAITING + modifiable=False) e NON avvia il DAG.
    """
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    # Avvisa se ci sono domande mancanti, ma non blocca la submit
    if not _all_questions_answered(lang):
        messages.warning(request, _t("You submitted with some unanswered questions. An admin will review before approval."))

    changed = Answer.objects.filter(language=lang).update(
        status=AnswerStatus.WAITING, modifiable=False
    )
    messages.success(request, _t(f"Submitted {changed} answers for approval."))
    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_approve(request, lang_id):
    """
    ADMIN: Approva e avvia il DAG SOLO se tutte le domande attive hanno risposta.
    """
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to perform this action."))
        return redirect("language_list")

    lang = get_object_or_404(Language, pk=lang_id)

    # Regola: tutte risposte devono esserci
    if not _all_questions_answered(lang):
        messages.error(request, _t("Impossibile approvare: ci sono domande senza risposta. Completa tutte le risposte prima di avviare il DAG."))
        return redirect("language_data", lang_id=lang.id)

    # Approva solo ciò che è in WAITING; resta modifiable=False
    changed = Answer.objects.filter(language=lang, status=AnswerStatus.WAITING).update(
        status=AnswerStatus.APPROVED, modifiable=False
    )

    # Log decisione di approvazione
    LanguageReview.objects.create(language=lang, decision="approve", created_by=request.user)

    # Avvia il DAG
    try:
        report = run_dag_for_language(lang_id)
        msg = _t(
            "Approved %(n)d answers. DAG: processed %(p)d, forced_to_zero %(fz)d, missing_orig %(mo)d, warnings %(wp)d."
        ) % {
            "n": changed,
            "p": len(report.processed or []),
            "fz": len(report.forced_zero or []),
            "mo": len(report.missing_orig or []),
            "wp": len(report.warnings_propagated or []),
        }
        if report.parse_errors:
            msg += " ParseErrors: " + ", ".join(f"{pid}" for (pid, _, _) in report.parse_errors[:6])
        messages.success(request, msg)
    except Exception as e:
        messages.warning(request, _t("Approved, but DAG failed: %(err)s") % {"err": str(e)})

    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_reject(request, lang_id):
    """
    ADMIN: Reject SEMPRE consentito, anche senza submit finale.
    Riapre l'editing all'utente (tutte le risposte diventano REJECTED + modifiable=True).
    Registra messaggio facoltativo.
    """
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to perform this action."))
        return redirect("language_list")

    lang = get_object_or_404(Language, pk=lang_id)
    message = (request.POST.get("message") or "").strip()

    with transaction.atomic():
        # Porta tutte le answers allo stato REJECTED e riapri editing
        changed = Answer.objects.filter(language=lang).update(
            status=AnswerStatus.REJECTED, modifiable=True
        )
        # Log decisione di reject (con messaggio opzionale)
        LanguageReview.objects.create(language=lang, decision="reject", message=message, created_by=request.user)

    if changed == 0:
        messages.info(request, _t("Nothing to reject."))
    else:
        messages.success(request, _t(f"Rejected submission. {changed} answers are editable again."))
    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_reopen(request, lang_id):
    """
    USER: su stato rejected può riaprire (torna pending/modifiable=True).
    """
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    changed = Answer.objects.filter(language=lang, status=AnswerStatus.REJECTED).update(
        status=AnswerStatus.PENDING, modifiable=True
    )
    if changed == 0:
        messages.info(request, _t("Nothing to reopen."))
    else:
        messages.success(request, _t(f"Reopened: {changed} answers set to pending."))
    return redirect("language_data", lang_id=lang.id)


@login_required
def language_export_xlsx(request, lang_id: str):
    # --- Fetch lingua + autorizzazione coerente con tutta l'app ---
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        # 404 "soft" per non rivelare l'esistenza della risorsa
        raise Http404("Language not found")

    is_admin = _is_admin(request.user)

    # --- Dati base (ordinamento coerente con UI) ---
    params = (
        ParameterDef.objects
        .filter(is_active=True)
        .order_by("position", "id")
    )

    # Domande per parametro 
    qs_by_param = {}
    for q in (
        Question.objects
        .select_related("parameter")
        .order_by("parameter__position", "id")   # opzionale: ordina come in UI
        # .order_by("parameter_id", "id")        # alternativa per non usare position
    ):
        qs_by_param.setdefault(q.parameter_id, []).append(q)


    # Risposte per lingua (indicizzate per question_id)
    answers = (
        Answer.objects
        .select_related("question")
        .filter(language_id=lang.id)
    )
    ans_by_qid = {a.question_id: a for a in answers}

    # Motivazioni in mappa id->label
    mot_map = {m.id: getattr(m, "label", getattr(m, "text", "")) for m in Motivation.objects.all()}

    # --- Esempi per lingua: indicizzati per question_id e ordinati ---
    ex_by_qid = {}
    examples = (
        Example.objects
        .select_related("answer")                # serve per accedere a answer.question_id
        .filter(answer__language_id=lang.id)     # <-- FIX: niente language_id diretto su Example
    )
    for ex in examples:
        qid = ex.answer.question_id
        ex_by_qid.setdefault(qid, []).append(ex)

    for arr in ex_by_qid.values():
        # ordina per numero, gestendo stringhe/non numerici
        def _as_int(v):
            try:
                return int(v)
            except Exception:
                return 10**9
        arr.sort(key=lambda e: _as_int(getattr(e, "number", "")))


    # === Workbook ===
    wb = Workbook()

    # Header fogli
    ans_header = [
        "Language ID", "Parameter Label", "Question ID", "Question",
        "Question status", "Answer", "Parameter value", "Motivation", "Comments"
    ]
    ex_header = [
        "Language ID", "Question ID", "Example #",
        "Data", "Transliteration", "Gloss", "English translation", "Reference"
    ]

    bold_white = Font(bold=True, color="FFFFFF")

    def _style_table(ws, name: str):
        max_col, max_row = ws.max_column, ws.max_row
        if max_row < 2:
            return
        ref = f"A1:{get_column_letter(max_col)}{max_row}"
        tbl = Table(displayName=name, ref=ref)
        tbl.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False
        )
        ws.add_table(tbl)
        ws.freeze_panes = "A2"
        widths = (
            [14, 18, 12, 36, 18, 10, 16, 28, 26]  # Answers
            if name == "Answers"
            else [14, 12, 12, 36, 20, 20, 26, 24]  # Examples
        )
        for idx, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = w

    # === Foglio Examples: sempre presente (admin e user) ===
    ws_examples = wb.active
    ws_examples.title = "Examples"
    ws_examples.append(ex_header)
    for i in range(1, len(ex_header) + 1):
        ws_examples.cell(row=1, column=i).font = bold_white

    for p in params:
        for q in qs_by_param.get(p.id, []):
            for ex in ex_by_qid.get(q.id, []):
                ws_examples.append([
                    lang.id,
                    q.id,
                    getattr(ex, "number", ""),             # <-- numero esempio
                    getattr(ex, "textarea", ""),           # Data
                    getattr(ex, "transliteration", ""),
                    getattr(ex, "gloss", ""),
                    getattr(ex, "translation", ""),
                    getattr(ex, "reference", ""),
                ])
    _style_table(ws_examples, "Examples")

    # === Foglio Answers: solo per admin ===
    if is_admin:
        ws_answers = wb.create_sheet("Answers", 0)  # Answers come primo foglio
        ws_answers.append(ans_header)
        for i in range(1, len(ans_header) + 1):
            ws_answers.cell(row=1, column=i).font = bold_white

        def _pretty_qc_from_status(status: str | None) -> str:
            s = (status or "").lower()
            if s == "approved":
                return "Done"
            if s in {"waiting_for_approval", "waiting"}:
                return "Needs review"
            return "Not compiled"

        for p in params:
            p_label = getattr(p, "name", getattr(p, "label", p.id))
            for q in qs_by_param.get(p.id, []):
                a = ans_by_qid.get(q.id)
                if a:
                    # motivazioni via through AnswerMotivation
                    ids = list(
                        AnswerMotivation.objects
                        .filter(answer=a)
                        .values_list("motivation_id", flat=True)
                    )
                    mot_text = "; ".join(mot_map.get(i, str(i)) for i in ids)

                    ws_answers.append([
                        lang.id,
                        p_label,
                        q.id,
                        getattr(q, "text", ""),
                        _pretty_qc_from_status(getattr(a, "status", None)),  # <-- QC da Answer.status
                        getattr(a, "response_text", ""),
                        getattr(a, "param_value", ""),
                        mot_text,
                        getattr(a, "comments", ""),
                    ])
                else:
                    ws_answers.append([
                        lang.id,
                        p_label,
                        q.id,
                        getattr(q, "text", ""),
                        "Not compiled",
                        "",
                        "",
                        "",
                        "",
                    ])
        _style_table(ws_answers, "Answers")

    # === Response ===
    ts = now().strftime("%Y%m%d")
    suffix = "full" if is_admin else "examples"
    filename = f"PCM_{lang.id}_{suffix}_{ts}.xlsx"
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp
