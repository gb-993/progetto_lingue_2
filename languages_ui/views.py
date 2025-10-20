
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
from django.utils.translation import gettext as _t
from django.urls import reverse

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

from core.models import LanguageReview 

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


# -----------------------
# List / CRUD lingua
# -----------------------
# languages_ui/views.py — SOSTITUISCI l'intera language_list con questa

@login_required
def language_list(request):
    from django.db.models import Max, Q
    q = (request.GET.get("q") or "").strip()
    user = request.user
    is_admin = _is_admin(user)

    # Annotiamo l'ultima modifica proveniente dalle Answer
    qs = (
        Language.objects
        .select_related("assigned_user")
        .annotate(last_change=Max("answers__updated_at"))
        .order_by("position")
    )

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
            | Q(family__icontains=q)
            | Q(top_level_family__icontains=q)
            | Q(source__icontains=q)
        )

        # match grezzo per booleano ("hist", "stor", "true"/"false")
        if q.lower() in {"hist", "stor", "storica", "storico", "true", "yes"}:
            filt |= Q(historical_language=True)
        if q.lower() in {"false", "no"}:
            filt |= Q(historical_language=False)

        if is_admin:
            filt |= Q(assigned_user__email__icontains=q)
        qs = qs.filter(filt)

    ctx = {
        "languages": qs,
        "page_obj": None,
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
    """
    Pagina di compilazione dati per una lingua.

    - Accesso: admin sempre; altrimenti la lingua deve essere assegnata all'utente (FK o M2M).
    - Prefetch:
        * Parametri attivi (ordinati per position)
        * Domande per parametro
        * Through "allowed_motivation_links" (ordinato per position, con motivation prefetchata)
    - Per ogni domanda costruiamo:
        * q.allowed_motivations_list -> lista di Motivation ordinate per position
        * q.ans -> SimpleNamespace con risposta, commenti, motivazioni, esempi, id answer
    - Calcoliamo un "semaforo" per parametro (ok/warn/missing) in base alle risposte yes/no.
    - Esplicitamente **NON** limitiamo più gli esempi a YES: il template/JS li mostra per YES e NO;
      il backend già salva/elimina esempi indipendentemente dal valore della risposta.
    """
    user = request.user
    is_admin = _is_admin(user)  # definita altrove nel file

    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(user, lang):  # definita altrove nel file
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    # === Prefetch ===
    # - Domande per parametro
    # - Through allowed_motivation_links con motivation in select_related e ordinati per position
    questions_qs = Question.objects.order_by("id")
    through_qs = (
        QuestionAllowedMotivation.objects
        .select_related("motivation")
        .order_by("position", "id")
    )

    parameters = (
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .prefetch_related(
            Prefetch("questions", queryset=questions_qs),
            Prefetch("questions__allowed_motivation_links", queryset=through_qs, to_attr="pref_links"),
        )
    )

    # === Risposte ed esempi per questa lingua ===
    answers_qs = (
        Answer.objects
        .filter(language=lang)
        .select_related("question")
        .prefetch_related("answer_motivations__motivation", "examples")
    )
    answers_by_qid = {a.question_id: a for a in answers_qs}

    # === Arricchisci le domande con motivazioni ordinate e stato per parametro ===
    for p in parameters:
        total = 0
        answered = 0

        for q in p.questions.all():
            total += 1

            # 1) Motivazioni per la domanda (ordinate per position)
            links = getattr(q, "pref_links", [])  # creato da Prefetch(to_attr="pref_links")
            q.allowed_motivations_list = [l.motivation for l in links] if links else []

            # 2) Risposta/Commenti/Motivazioni/Esempi (se presenti)
            a = answers_by_qid.get(q.id)
            if a:
                q.ans = SimpleNamespace(
                    response_text=(a.response_text or ""),
                    comments=(a.comments or ""),
                    motivation_ids=[am.motivation_id for am in a.answer_motivations.all()],
                    examples=list(a.examples.all()),
                    answer_id=a.id,
                )
                if a.response_text in ("yes", "no"):
                    answered += 1
            else:
                q.ans = SimpleNamespace(
                    response_text="",
                    comments="",
                    motivation_ids=[],
                    examples=[],
                    answer_id=None,
                )

        # 3) Stato sintetico per parametro (per colorare i "quadratini" wizard)
        if total == 0:
            p.status = "ok"
        elif answered == 0:
            p.status = "missing"
        elif answered < total:
            p.status = "warn"
        else:
            p.status = "ok"

        # palette (se già usata dal template)
        if p.status == "ok":
            p.bg_color = "#d4edda"
            p.fg_color = "#155724"
        elif p.status == "warn":
            p.bg_color = "#fff3cd"
            p.fg_color = "#856404"
        else:
            p.bg_color = "#f8d7da"
            p.fg_color = "#721c24"

    # === Verifica completezza (tutte le domande attive hanno YES/NO) ===
    active_q_total = 0
    active_q_answered = 0
    for p in parameters:
        for q in p.questions.all():
            active_q_total += 1
            if getattr(q, "ans", None) and q.ans.response_text in ("yes", "no"):
                active_q_answered += 1
    all_answered = (active_q_total > 0 and active_q_answered == active_q_total)

    # === Stato complessivo e ultimo reject ===
    lang_status = _language_overall_status(lang)  # definita altrove
    last_reject = (
        LanguageReview.objects.filter(language=lang, decision="reject")
        .order_by("-created_at")
        .first()
    )

    ctx = {
        "language": lang,
        "parameters": parameters,
        "is_admin": is_admin,
        "all_answered": all_answered,
        "lang_status": lang_status,
        "last_reject": last_reject,
    }
    return render(request, "languages/data.html", ctx)


# -----------------------
# Salvataggio risposte
# -----------------------

@login_required
@require_http_methods(["POST"])
@transaction.atomic
def parameter_save(request, lang_id, param_id):
    """
    Salvataggio in bulk di tutte le risposte del parametro selezionato.
    Dopo il salvataggio reindirizza automaticamente al parametro successivo
    (in base a 'position'); se non esiste, resta su quello corrente.
    """
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    param = get_object_or_404(ParameterDef, pk=param_id, is_active=True)
    questions = list(param.questions.all())

    saved_count = 0
    for q in questions:
        resp_key = f"resp_{q.id}"
        response_text = (request.POST.get(resp_key) or "").strip().lower()
        if response_text not in ("yes", "no"):
            continue

        comments = (request.POST.get(f"com_{q.id}") or "").strip()

        answer = (
            Answer.objects.select_for_update()
            .filter(language=lang, question=q)
            .first()
        )
        if answer and not answer.modifiable and not _is_admin(request.user):
            continue
        if answer is None:
            answer = Answer(language=lang, question=q)

        answer.response_text = response_text
        answer.comments = comments
        answer.save()
        saved_count += 1

        # --- Motivazioni (rispettando allowed e esclusività MOT1) ---
        try:
            motivation_ids = [int(x) for x in request.POST.getlist(f"mot_{q.id}")]
        except ValueError:
            motivation_ids = []

        allowed_ids = set(
            QuestionAllowedMotivation.objects.filter(question=q)
            .values_list("motivation_id", flat=True)
        )
        mot1 = Motivation.objects.filter(code="MOT1").only("id").first()

        if response_text == "yes":
            target_ids = set()
        else:
            filtered = [mid for mid in motivation_ids if mid in allowed_ids]
            target_ids = {mot1.id} if (mot1 and mot1.id in filtered) else set(filtered)

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

        # --- Esempi: delete/update/create ---
        FIELDS = {"number", "textarea", "transliteration", "gloss", "translation", "reference"}

        # delete
        del_ids = []
        for key, val in request.POST.items():
            if key.startswith("del_ex_") and val == "1":
                try:
                    del_ids.append(int(key.split("_", 2)[2]))
                except ValueError:
                    pass
        if del_ids:
            Example.objects.filter(answer=answer, id__in=del_ids).delete()

        # update esistenti
        for key, val in request.POST.items():
            if not key.startswith("ex_"):
                continue
            try:
                _ex, ex_id_str, field = key.split("_", 2)
                ex_id = int(ex_id_str)
            except ValueError:
                continue
            if field not in FIELDS:
                continue
            Example.objects.filter(id=ex_id, answer=answer).update(**{field: (val or "").strip()})

        # nuovi esempi
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

    # Messaggio e calcolo del prossimo parametro
    messages.success(request, _t(f"Saved {saved_count} answers for parameter {param.id}."))

    next_param = (
        ParameterDef.objects
        .filter(is_active=True, position__gt=param.position)
        .order_by("position")
        .first()
    )
    target_id = next_param.id if next_param else param.id
    return redirect(f"{reverse('language_data', kwargs={'lang_id': lang.id})}#p-{target_id}")



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
    return redirect(f"{reverse('language_data', kwargs={'lang_id': lang.id})}#p-{question.id}")







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
    Debug per una lingua (solo admin):
      - Tabella unica con: ID domande, risposte yes/no, value_orig (+/-), value_eval (+/-/0),
        warning init/final, condizione raw/pretty e esito condizione (TRUE/FALSE).
      - Sezione diagnostica inferiore rimossa: i campi TRUE/FALSE sono integrati nella tabella principale.
    """
    user = request.user
    lang = get_object_or_404(Language, pk=lang_id)

    # Accesso
    if not _check_language_access(user, lang):
        get_object_or_404(Language, pk="__deny__")
    if not _is_admin(user):
        get_object_or_404(Language, pk="__deny__")

    # Parametri attivi + domande
    params = (
        ParameterDef.objects
        .filter(is_active=True)
        .order_by("position", "id")
        .prefetch_related(Prefetch("questions", queryset=Question.objects.order_by("id")))
    )

    # Risposte per lingua
    answers = (
        Answer.objects
        .filter(language=lang)
        .select_related("question")
        .order_by("question__parameter__position", "question_id")
    )
    answers_by_qid = {a.question_id: a for a in answers}

    # Valori iniziali/finali + warning
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

    # Diagnostica parser (per cond_true)
    diag_rows = diagnostics_for_language(lang)
    # d.param_id, d.cond_true, d.cond_raw, d.cond_pretty, d.value_orig, d.value_eval, d.note
    cond_map = {}
    for d in diag_rows:
        pid = getattr(d, "param_id", None) if not isinstance(d, dict) else d.get("param_id")
        cond_true = getattr(d, "cond_true", None) if not isinstance(d, dict) else d.get("cond_true")
        if pid:
            cond_map[pid] = cond_true  # True / False / None

    # Costruzione righe tabella principale (con cond_true)
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
            "cond_true": cond_map.get(p.id, None),   # <<< NUOVO CAMPO USATO DAL TEMPLATE
        })

    ctx = {
        "language": lang,
        "rows": rows,
        "is_admin": _is_admin(user),
    }
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

    return redirect("language_debug", lang_id=lang.id)


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
            status=AnswerStatus.REJECTED, modifiable=False
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
        .order_by("parameter__position", "id")
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
        .filter(answer__language_id=lang.id)
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

    # --- Valori parametro per lingua: orig + eval (se presente) ---
    lps_qs = LanguageParameter.objects.filter(language=lang).select_related("parameter")
    if HAS_EVAL:
        lps_qs = lps_qs.select_related("eval")

    value_orig_by_pid: dict[str, str] = {}
    value_eval_by_pid: dict[str, str] = {}
    for lp in lps_qs:
        pid = lp.parameter_id
        value_orig_by_pid[pid] = (lp.value_orig or "")
        if getattr(lp, "eval", None):
            value_eval_by_pid[pid] = (getattr(lp.eval, "value_eval", None) or "")
        else:
            value_eval_by_pid[pid] = ""

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
                    getattr(ex, "number", ""),             # Numero esempio
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
                # Valore parametro per questa domanda/parametro (prima eval, poi orig)
                param_value = (
                    value_eval_by_pid.get(q.parameter_id)
                    or value_orig_by_pid.get(q.parameter_id)
                    or ""
                )

                if a:
                    # motivazioni via through AnswerMotivation (liste ID -> testi)
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
                        _pretty_qc_from_status(getattr(a, "status", None)),  # QC da Answer.status
                        getattr(a, "response_text", ""),
                        param_value,
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
                        param_value,  # anche se non c'è answer, il valore parametro può esistere
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
