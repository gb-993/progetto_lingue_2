
from __future__ import annotations


from types import SimpleNamespace
import os
import tempfile  

import io
import zipfile
import threading          
import logging         
from django.conf import settings  
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command  
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Prefetch, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _t
from django.views.decorators.http import require_http_methods, require_POST
from django.http import HttpResponse, Http404, JsonResponse
from django.utils.timezone import now
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from django.utils.translation import gettext as _t
from django.urls import reverse
from datetime import datetime, time, date  
from django.utils import timezone   
from .forms import LanguageForm 


from core.models import (
    Language,
    ParameterDef,
    ParameterReviewFlag,
    Question,
    Answer,
    Example,
    Motivation,
    AnswerMotivation,
    QuestionAllowedMotivation,
    LanguageParameter,  
    ParameterReviewFlag,        
)
try:
    from core.models import LanguageParameterEval  
    HAS_EVAL = True
except Exception:
    LanguageParameterEval = None 
    HAS_EVAL = False  

try:
    from core.models import AnswerStatus  
except Exception:
    class AnswerStatus:
        PENDING = "pending"
        WAITING = "waiting_for_approval"
        APPROVED = "approved"
        REJECTED = "rejected"
--
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
    # Una query: GROUP BY status
    rows = (
        Answer.objects
        .filter(language=lang)
        .values("status")
        .annotate(c=Count("id"))
    )

    counts = {
        "pending": 0,
        "waiting_for_approval": 0,
        "approved": 0,
        "rejected": 0,
    }
    total = 0

    for r in rows:
        s = r["status"] or ""
        if s in counts:
            counts[s] += r["c"]
            total += r["c"]

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
    rows = (
        Answer.objects
        .filter(language=lang)
        .values("status")
        .annotate(c=Count("id"))
    )

    counts = {
        "pending": 0,
        "waiting": 0,
        "approved": 0,
        "rejected": 0,
    }

    # mappa status DB -> chiavi counts
    key_map = {
        AnswerStatus.PENDING: "pending",
        AnswerStatus.WAITING: "waiting",
        AnswerStatus.APPROVED: "approved",
        AnswerStatus.REJECTED: "rejected",
    }

    seen_status = set()
    for r in rows:
        status = r["status"]
        seen_status.add(status)
        key = key_map.get(status)
        if key:
            counts[key] += r["c"]

    if AnswerStatus.WAITING in seen_status:
        overall = AnswerStatus.WAITING
    elif AnswerStatus.APPROVED in seen_status:
        overall = AnswerStatus.APPROVED
    elif AnswerStatus.REJECTED in seen_status:
        overall = AnswerStatus.REJECTED
    else:
        overall = AnswerStatus.PENDING

    return {"overall": overall, "counts": counts}



def _all_questions_answered(language: Language) -> bool:
    """
    True se TUTTE le domande attive hanno una Answer yes/no per questa lingua.
    """
    active_qids = set(
        Question.objects.filter(parameter__is_active=True).values_list("id", flat=True)
    )
    if not active_qids:
        return False 
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

from django.db.models import Max, Q
from django.db.models.functions import Lower
from urllib.parse import urlencode
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def language_list(request):

    q = (request.GET.get("q") or "").strip()

    #parametri per ordinamento
    sort_key = (request.GET.get("sort") or "").strip()   # 'id' | 'name' | 'top' | ''
    sort_dir = (request.GET.get("dir") or "asc").strip() # 'asc' | 'desc'

    user = request.user
    is_admin = _is_admin(user)

    #  default order = position
    qs = (
        Language.objects
        .select_related("assigned_user")
        .annotate(last_change=Max("answers__updated_at"))
        .order_by("position")
    )

    if not is_admin:
        qs = qs.filter(Q(assigned_user=user) | Q(users=user))

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
        if q.lower() in {"hist", "stor", "storica", "storico", "true", "yes"}:
            filt |= Q(historical_language=True)
        if q.lower() in {"false", "no"}:
            filt |= Q(historical_language=False)
        if is_admin:
            filt |= Q(assigned_user__email__icontains=q)
        qs = qs.filter(filt)

    sort_map = {
        "id": "id",
        "name": "name_full",
        "top": "top_level_family",
    }

    active_sort = None
    if sort_key in sort_map:
        active_sort = sort_key

        if sort_key == "name":
            # case-insensitive
            qs = qs.annotate(_name_ci=Lower("name_full"))
            order_field = "_name_ci"
        elif sort_key == "top":
            # case-insensitive 
            qs = qs.annotate(_top_ci=Lower("top_level_family"))
            order_field = "_top_ci"
        else:
            order_field = sort_map[sort_key]

        # stabilità: a parità di campo, tieni position
        if sort_dir == "desc":
            qs = qs.order_by(f"-{order_field}", "position")
        else:
            qs = qs.order_by(order_field, "position")


    def _toggle_url(column: str) -> str:
        # se clicchi la stessa colonna, alterna asc/desc; altrimenti riparti asc
        next_dir = "desc" if (active_sort == column and sort_dir == "asc") else "asc"

        params = []
        if q:
            params.append(("q", q))
        params.append(("sort", column))
        params.append(("dir", next_dir))
        return "?" + urlencode(params)

    sort_urls = {
        "id": _toggle_url("id"),
        "name": _toggle_url("name"),
        "top": _toggle_url("top"),
    }

    ctx = {
        "languages": qs,
        "page_obj": None,
        "q": q,
        "is_admin": is_admin,

        "sort": active_sort,
        "dir": sort_dir,
        "sort_urls": sort_urls,
    }
    return render(request, "languages/list.html", ctx)





@login_required
@require_http_methods(["GET", "POST"])
def language_add(request):
    from .forms import LanguageForm  
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
    lang = get_object_or_404(Language, pk=lang_id)
    if request.method == "POST":
        form = LanguageForm(request.POST, instance=lang)
        if form.is_valid():
            form.save()
            messages.success(request, _t("Language updated."))
            return redirect("language_list")
    else:
        form = LanguageForm(instance=lang)
    return render(request, "languages/edit.html", {"page_title": "Edit language", "form": form, "language": lang})



@login_required
@require_POST
@transaction.atomic
def language_delete(request, lang_id: str):
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to perform this action."))
        return redirect("language_list")

    lang = get_object_or_404(Language, pk=lang_id)

    pwd = request.POST.get("admin_password") or ""
    if not request.user.check_password(pwd):
        messages.error(request, _t("Incorrect password. Deletion aborted."))
        return redirect("language_edit", lang_id=lang_id)

    lang.delete()
    messages.success(request, _t(f"Language “{lang_id}” and related data deleted."))
    return redirect("language_list")



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

    questions_qs = Question.objects.order_by("id")
    through_qs = QuestionAllowedMotivation.objects.select_related("motivation").order_by("position", "id")
    parameters = (
        ParameterDef.objects.filter(is_active=True)
        .order_by("position")
        .prefetch_related(
            Prefetch("questions", queryset=questions_qs),
            Prefetch("questions__allowed_motivation_links", queryset=through_qs, to_attr="pref_links"),
        )
    )

    answers_qs = (
        Answer.objects.filter(language=lang)
        .select_related("question")
        .prefetch_related("answer_motivations__motivation", "examples")
    )
    answers_by_qid = {a.question_id: a for a in answers_qs}

    flagged_pids = set(
        ParameterReviewFlag.objects.filter(language=lang, user=user, flag=True).values_list("parameter_id", flat=True)
    )

    active_q_total = 0
    active_q_answered = 0

    for p in parameters:
        total = 0
        answered = 0
        for q in p.questions.all():
            total += 1
            active_q_total += 1
            links = getattr(q, "pref_links", [])
            q.allowed_motivations_list = [l.motivation for l in links] if links else []
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
                    active_q_answered += 1
            else:
                q.ans = SimpleNamespace(response_text="", comments="", motivation_ids=[], examples=[], answer_id=None)

        is_touched = answered > 0
        is_complete = (total > 0 and answered == total)
        is_flagged = p.id in flagged_pids

        if not is_touched:
            p.status = "untouched"
            p.bg_color = "transparent"
            p.fg_color = "inherit"
        elif is_complete and not is_flagged:
            p.status = "ok"
            p.bg_color = "#e6f7e9"
            p.fg_color = "#0f5132"
        else:
            p.status = "red"
            p.bg_color = "#ffe8e8"
            p.fg_color = "#842029"

    all_answered = (active_q_total > 0 and active_q_answered == active_q_total)
    lang_status = _language_overall_status(lang)
    last_reject = (
        LanguageReview.objects.filter(language=lang, decision="reject").order_by("-created_at").first()
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


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def parameter_save(request, lang_id, param_id):

    try:
        lang = Language.objects.select_for_update().get(pk=lang_id)
    except Language.DoesNotExist:
        messages.warning(request, _t("This language was deleted while you were saving. Your changes were not saved."))
        return redirect("language_list")
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

    param = get_object_or_404(ParameterDef, pk=param_id, is_active=True)
    questions = list(param.questions.all())

    saved_count = 0
    FIELDS = {"number", "textarea", "transliteration", "gloss", "translation", "reference"}

    for q in questions:
        response_text = (request.POST.get(f"resp_{q.id}") or "").strip().lower()
        comments = (request.POST.get(f"com_{q.id}") or "").strip()

        if response_text not in ("yes", "no"):
            continue

        # Lock dell'Answer se esiste (evita corse su update concorrenti); se non esiste, la creiamo.
        answer = (
            Answer.objects.select_for_update()
            .filter(language=lang, question=q)
            .first()
        )
        if answer is None:
            answer = Answer(language=lang, question=q)

        del_ids = []
        for key, val in request.POST.items():
            if key.startswith("del_ex_") and (val or "").strip() == "1":
                try:
                    del_ids.append(int(key.split("_", 2)[2]))
                except ValueError:
                    pass

        updated_textareas = {}
        for key, val in request.POST.items():
            if not key.startswith("ex_"):
                continue
            try:
                _ex, ex_id, field = key.split("_", 2)
                ex_id = int(ex_id)
            except ValueError:
                continue
            if field == "textarea":
                updated_textareas[ex_id] = (val or "").strip()

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

        if response_text == "yes":
            has_textarea_final = False
            existing_qs = Example.objects.filter(answer__language=lang, answer__question=q)
            existing_map = {ex.id: ex for ex in existing_qs}
            for ex_id, ex in existing_map.items():
                if ex_id in del_ids:
                    continue
                tx = updated_textareas.get(ex_id, (ex.textarea or "").strip())
                if tx:
                    has_textarea_final = True
                    break
            if not has_textarea_final and buckets:
                for _uid, data in buckets.items():
                    if (data.get("textarea") or "").strip():
                        has_textarea_final = True
                        break
            if not has_textarea_final:
                messages.error(request, _t("If you answer YES, you must provide at least one example with a non-empty text."))
                return redirect(f"{reverse('language_data', kwargs={'lang_id': lang.id})}#p-{param.id}")

        answer.response_text = response_text
        answer.comments = comments
        answer.save()
        saved_count += 1

        try:
            target_ids = {int(x) for x in request.POST.getlist(f"mot_{q.id}")}
        except ValueError:
            target_ids = set()
        allowed_ids = set(
            QuestionAllowedMotivation.objects.filter(question=q).values_list("motivation_id", flat=True)
        )
        target_ids &= allowed_ids
        current_ids = set(AnswerMotivation.objects.filter(answer=answer).values_list("motivation_id", flat=True))
        to_add = target_ids - current_ids
        to_del = current_ids - target_ids
        if to_add:
            AnswerMotivation.objects.bulk_create(
                [AnswerMotivation(answer=answer, motivation_id=mid) for mid in to_add],
                ignore_conflicts=True,
            )
        if to_del:
            AnswerMotivation.objects.filter(answer=answer, motivation_id__in=to_del).delete()

        if del_ids:
            Example.objects.filter(answer=answer, id__in=del_ids).delete()

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

    action = (request.POST.get("action") or "save").strip().lower()
    try:
        if action == "next":
            ParameterReviewFlag.objects.update_or_create(
                language=lang, parameter=param, user=request.user, defaults={"flag": True}
            )
        else:
            ParameterReviewFlag.objects.update_or_create(
                language=lang, parameter=param, user=request.user, defaults={"flag": False}
            )
    except Exception:
        pass

    messages.success(request, _t(f"Saved {saved_count} answers for parameter {param.id}."))
    next_param = (
        ParameterDef.objects.filter(is_active=True, position__gt=param.position).order_by("position").first()
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

    # 1) Input di base
    response_text = (request.POST.get("response_text") or "").strip().lower()
    if response_text not in ("yes", "no"):
        messages.error(request, _t("Invalid answer value."))
        return redirect("language_data", lang_id=lang.id)

    comments = (request.POST.get("comments") or "").strip()

    # 2) Lock/crea Answer
    answer = (
        Answer.objects.select_for_update()
        .filter(language=lang, question=question)
        .first()
    )
    if answer and not answer.modifiable and not _is_admin(request.user):
        messages.error(request, _t("This answer is locked (waiting/approved)."))
        return redirect("language_data", lang_id=lang.id)
    if answer is None:
        answer = Answer(language=lang, question=question)

    # 3) Salva header
    answer.response_text = response_text
    answer.comments = comments
    answer.save()

    # 4) Motivazioni
    try:
        motivation_ids = {int(x) for x in request.POST.getlist("motivation_ids")}
    except ValueError:
        motivation_ids = set()

    allowed_ids = set(
        QuestionAllowedMotivation.objects.filter(question=question).values_list("motivation_id", flat=True)
    )
    motivation_ids &= allowed_ids

    current_ids = set(AnswerMotivation.objects.filter(answer=answer).values_list("motivation_id", flat=True))
    to_add = motivation_ids - current_ids
    to_del = current_ids - motivation_ids
    if to_add:
        AnswerMotivation.objects.bulk_create(
            [AnswerMotivation(answer=answer, motivation_id=mid) for mid in to_add],
            ignore_conflicts=True,
        )
    if to_del:
        AnswerMotivation.objects.filter(answer=answer, motivation_id__in=to_del).delete()

    # 5) ESEMPI: raccolta mutazioni + VALIDAZIONE + applicazione (singola domanda)
    FIELDS = {"number", "textarea", "transliteration", "gloss", "translation", "reference"}

    # 5.1) Raccolta delete
    del_ids = []
    for key, val in request.POST.items():
        if not key.startswith("del_ex_"):
            continue
        if (val or "").strip() != "1":
            continue
        try:
            del_ids.append(int(key.split("_", 2)[2]))
        except ValueError:
            pass

    # 5.2) Raccolta update delle textarea esistenti
    updated_textareas = {}
    for key, val in request.POST.items():
        if not key.startswith("ex_"):
            continue
        try:
            _ex, ex_id, field = key.split("_", 2)
            ex_id = int(ex_id)
        except ValueError:
            continue
        if field == "textarea":
            updated_textareas[ex_id] = (val or "").strip()

    # 5.3) Raccolta nuovi esempi
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

    # 5.4) VALIDAZIONE per YES
    if response_text == "yes":
        has_nonempty_textarea = False

        existing_qs = Example.objects.filter(answer=answer).exclude(id__in=del_ids).only("id", "textarea")
        for ex in existing_qs:
            final_txt = updated_textareas.get(ex.id, (ex.textarea or ""))
            if final_txt.strip():
                has_nonempty_textarea = True
                break

        if not has_nonempty_textarea:
            for _uid, data in buckets.items():
                if (data.get("textarea") or "").strip():
                    has_nonempty_textarea = True
                    break

        if not has_nonempty_textarea:
            messages.error(
                request,
                _t(f"Question {question.id}: with YES you must provide at least one example with a non-empty Example text.")
            )
            transaction.set_rollback(True)
            return redirect(f"{reverse('language_data', kwargs={'lang_id': lang.id})}#p-{question.parameter_id}")

    # 5.5) APPLICAZIONE MUTAZIONI

    # delete
    if del_ids:
        Example.objects.filter(answer=answer, id__in=del_ids).delete()

    # update esistenti (tutti i campi)
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

    # create nuovi
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

    messages.success(request, _t("Answer saved."))
    return redirect(f"{reverse('language_data', kwargs={'lang_id': lang.id})}#p-{question.parameter_id}")





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

    diag_rows = diagnostics_for_language(lang)
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
            "cond_true": cond_map.get(p.id, None),  
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

    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        messages.error(request, _t("You don't have access to this language."))
        return redirect("language_list")

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
        LanguageReview.objects.create(language=lang, decision="reject", message=message, created_by=request.user)

    if changed == 0:
        messages.info(request, _t("Nothing to reject."))
    else:
        messages.success(request, _t(f"Rejected submission. {changed} answers are editable again."))
    return redirect("language_data", lang_id=lang.id)


@login_required
@require_POST
def language_reopen(request, lang_id):

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




# === API per review flag (riuso di ParameterReviewFlag) =================

@login_required
@require_http_methods(["GET"])
def review_flags_list(request, lang_id: str):
    """
    Ritorna i param id marcati 'torno dopo' dall'utente corrente per la lingua data.
    """
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        return JsonResponse({"flags": []})
    flags = list(
        ParameterReviewFlag.objects.filter(language=lang, user=request.user, flag=True)
        .values_list("parameter_id", flat=True)
    )
    return JsonResponse({"flags": flags})


@login_required
@require_http_methods(["POST"])
def toggle_review_flag(request, lang_id: str, param_id: str):
    """
    Imposta/rimuove il flag 'torno dopo' per l'utente corrente sul parametro dato.
    """
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    param = get_object_or_404(ParameterDef, pk=param_id, is_active=True)
    flag = (request.POST.get("flag") or "").strip() == "1"
    ParameterReviewFlag.objects.update_or_create(
        language=lang, parameter=param, user=request.user, defaults={"flag": flag}
    )
    return JsonResponse({"ok": True, "flag": flag})


       
from datetime import datetime, time
from django.utils import timezone
from django.db.models import Max, Q

@login_required
@require_http_methods(["GET"])
def language_list_export_xlsx(request):
    """
    Excel export for Languages: fixed, explicit columns in a site-coherent order.
    - Removes 'position'
    - Serializes assigned user (full name + email)
    - Adds 'data last change' from answers' last update
    """
    q = (request.GET.get("q") or "").strip()
    user = request.user
    is_admin = _is_admin(user)

    qs = (
        Language.objects
        .select_related("assigned_user")
        .annotate(last_change=Max("answers__updated_at"))
        .order_by("position")  
    )
    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(name_full__icontains=q) |
            Q(top_level_family__icontains=q) |
            Q(family__icontains=q) |
            Q(grp__icontains=q) |
            Q(isocode__icontains=q) |
            Q(glottocode__icontains=q) |
            Q(source__icontains=q)
        )

    if not is_admin:
        qs = qs.filter(Q(assigned_user=user) | Q(users=user)).distinct()

    def _xlsx_sanitize(v):
        if v is None:
            return ""
        if isinstance(v, bool):
            return "Yes" if v else "No"
        if isinstance(v, datetime):
            if timezone.is_aware(v):
                v = timezone.localtime(v)
            return v.replace(tzinfo=None)
        if isinstance(v, time):
            return v.replace(tzinfo=None) if v.tzinfo else v
        return v

    def _full_name(u):
        if not u:
            return ""
        nm = f"{(u.name or '').strip()} {(u.surname or '').strip()}".strip()
        return nm or (u.email or "")

    def _email(u):
        return "" if not u else (u.email or "")

    HEADERS = [
        "ID",
        "Name",
        "Top-level family",
        "Family",
        "Group",
        "Glottocode",
        "ISO code",
        "Historical",
        "Source",
        "Assigned user",
        "Email",
        "Date last change",
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Languages"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # rows
    for L in qs.iterator():
        row = [
            _xlsx_sanitize(L.id),
            _xlsx_sanitize(L.name_full),
            _xlsx_sanitize(L.top_level_family),
            _xlsx_sanitize(L.family),
            _xlsx_sanitize(L.grp),
            _xlsx_sanitize(L.glottocode),
            _xlsx_sanitize(L.isocode),
            _xlsx_sanitize(L.historical_language),
            _xlsx_sanitize(L.source),
            _xlsx_sanitize(_full_name(L.assigned_user)),
            _xlsx_sanitize(_email(L.assigned_user)),
            _xlsx_sanitize(L.last_change),
        ]
        ws.append(row)

    from openpyxl.utils import get_column_letter
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 8
        for cell in ws[col_letter]:
            val = cell.value
            if val is None:
                continue
            max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

    ts = timezone.localtime(timezone.now()).strftime("%Y%m%d")
    filename = f"PCM_languages_{ts}.xlsx"
    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


logger = logging.getLogger(__name__)  
def _run_import_language_from_excel_bg(tmp_path: str, original_name: str, user_id: int | None):
    """
    Esegue il management command import_language_from_excel in background
    e cancella il file temporaneo alla fine.
    """
    try:
        logger.info(
            "Starting Excel import in background: file=%s, user_id=%s",
            original_name,
            user_id,
        )
        # equiv. a: python manage.py import_language_from_excel --file <tmp_path>
        call_command("import_language_from_excel", file=tmp_path)
        logger.info("Excel import COMPLETED: file=%s", original_name)
    except Exception:
        logger.exception("Excel import FAILED: file=%s", original_name)
    finally:
        try:
            os.remove(tmp_path)
            logger.info("Temporary file deleted: %s", tmp_path)
        except OSError:
            logger.warning("Could not delete temporary file: %s", tmp_path)




@login_required
@require_http_methods(["GET", "POST"])
def language_import_excel(request):
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to perform this action."))
        return redirect("language_list")

    if request.method == "POST":
        print("FILES:", request.FILES)
        print("POST:", request.POST)
        upload = request.FILES.get("file")
        if not upload:
            messages.error(request, _t("You must select an Excel file to import."))
            return redirect("language_import_excel")

        filename = (upload.name or "").lower()
        if not filename.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
            messages.error(request, _t("Unsupported file type. Please upload an .xlsx file."))
            return redirect("language_import_excel")

        # Salva su file temporaneo e lancia il command in BACKGROUND
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                for chunk in upload.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Thread in background che esegue il command e poi cancella il file
            t = threading.Thread(
                target=_run_import_language_from_excel_bg,
                args=(tmp_path, upload.name, getattr(request.user, "id", None)),
                daemon=True,
            )
            t.start()

            # Messaggio per l'admin: import avviato, puoi controllare più tardi
            messages.info(
                request,
                _t(
                    "Import started in background for file “%(fname)s”. "
                    "You can go back to the Languages list and, after some time, "
                    "reload the page to see the imported data."
                ) % {"fname": upload.name}
            )

            # Pagina di conferma con stato "import_started"
            return render(
                request,
                "languages/import_excel.html",
                {
                    "import_started": True,          # NUOVO flag per il template
                    "uploaded_filename": upload.name,
                },
            )

        except Exception as e:
            # In caso di errore PRIMA di lanciare il thread (es. problemi I/O)
            logger.exception("Error scheduling Excel import")
            messages.error(
                request,
                _t("Import could not be started: %(err)s") % {"err": str(e)},
            )
            return redirect("language_import_excel")

    # GET: mostra form di upload (stato iniziale, nessun import_started)
    return render(request, "languages/import_excel.html", {})



def _build_language_workbook(lang: Language, user):
    """
    Costruisce il Workbook Excel per UNA lingua, riusato da:
    - export singolo (language_export_xlsx)
    - export totale ZIP (language_export_all_zip)
    Ritorna: (workbook, suffix)
    suffix = "full" se admin, altrimenti "examples".
    """
    is_admin = _is_admin(user)

    # Parametri attivi
    params = (
        ParameterDef.objects
        .filter(is_active=True)
        .order_by("position", "id")
    )

    # Domande per parametro
    qs_by_param: dict[str, list[Question]] = {}
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

    # Motivazioni in mappa id->label (per foglio Answers)
    mot_map = {
        m.id: getattr(m, "label", getattr(m, "text", ""))
        for m in Motivation.objects.all()
    }

    # --- Esempi per lingua: indicizzati per question_id e ordinati ---
    ex_by_qid: dict[str, list[Example]] = {}
    examples = (
        Example.objects
        .select_related("answer")
        .filter(answer__language_id=lang.id)
    )
    for ex in examples:
        qid = ex.answer.question_id
        ex_by_qid.setdefault(qid, []).append(ex)

    # Ordinamento per "number" numerico quando possibile
    for arr in ex_by_qid.values():
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

    # Header fogli esistenti
    ans_header = [
        "Language ID", "Parameter Label", "Question ID", "Question",
        "Question status", "Answer", "Parameter value", "Motivation", "Comments",
    ]
    ex_header = [
        "Language ID", "Question ID", "Example #",
        "Example text", "Transliteration", "Gloss", "English translation", "Reference",
    ]

    # Header per foglio compatibile con import_language_from_excel
    upload_header = [
        "Language",
        "Parameter_Label",
        "Question_ID",
        "Question",
        "Question_Examples_YES",
        "Question_Intructions_Comments",
        "Language_Answer",
        "Language_Comments",
        "Language_Examples",
        "Language_Example_Gloss",
        "Language_Example_Translation",
        "Language_References",
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
            showRowStripes=True, showColumnStripes=False,
        )
        ws.add_table(tbl)
        ws.freeze_panes = "A2"
        widths = (
            [14, 18, 12, 36, 18, 10, 16, 28, 26]  # Answers
            if name == "Answers"
            else [14, 12, 12, 36, 20, 20, 26, 24]  # Examples / Upload
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
                    getattr(ex, "number", ""),
                    getattr(ex, "textarea", ""),
                    getattr(ex, "transliteration", ""),
                    getattr(ex, "gloss", ""),
                    getattr(ex, "translation", ""),
                    getattr(ex, "reference", ""),
                ])
    _style_table(ws_examples, "Examples")

    # === Fogli aggiuntivi solo per admin ===
    if is_admin:
        # ----------------------------
        # Foglio Database_model (compatibile con l'IMPORT)
        # ----------------------------
        ws_upload = wb.create_sheet("Database_model", 0)  # primo foglio
        ws_upload.append(upload_header)
        for col_idx in range(1, len(upload_header) + 1):
            ws_upload.cell(row=1, column=col_idx).font = bold_white

        # Costruzione righe nel formato atteso da import_language_from_excel
        for p in params:
            p_label = p.id
            for q in qs_by_param.get(p.id, []):
                a = ans_by_qid.get(q.id)

                # Language_Answer: YES / NO / vuoto
                if a and a.response_text == "yes":
                    lang_answer = "YES"
                elif a and a.response_text == "no":
                    lang_answer = "NO"
                else:
                    lang_answer = ""

                lang_comments = getattr(a, "comments", "") if a else ""

                # Aggregazione esempi in celle multilinea
                ex_list = ex_by_qid.get(q.id, [])
                examples_lines: list[str] = []
                gloss_lines: list[str] = []
                transl_lines: list[str] = []
                ref_lines: list[str] = []

                for idx_ex, ex in enumerate(ex_list):
                    num = (getattr(ex, "number", "") or "").strip()
                    if not num:
                        num = str(idx_ex + 1)
                    text = getattr(ex, "textarea", "") or ""
                    if text:
                        examples_lines.append(f"{num}. {text}")
                    else:
                        examples_lines.append(num)

                    gloss_lines.append(getattr(ex, "gloss", "") or "")
                    transl_lines.append(getattr(ex, "translation", "") or "")
                    ref_lines.append(getattr(ex, "reference", "") or "")

                cell_examples = "\n".join(examples_lines) if examples_lines else ""
                cell_gloss = "\n".join(gloss_lines) if gloss_lines else ""
                cell_transl = "\n".join(transl_lines) if transl_lines else ""
                cell_refs = "\n".join(ref_lines) if ref_lines else ""

                ws_upload.append([
                    # Language: il command di import usa name_full in colonna "Language"
                    lang.name_full,
                    p_label,
                    q.id,
                    getattr(q, "text", "") or "",
                    getattr(q, "example_yes", "") or "",
                    getattr(q, "instruction", "") or "",
                    lang_answer,
                    lang_comments,
                    cell_examples,
                    cell_gloss,
                    cell_transl,
                    cell_refs,
                ])

        _style_table(ws_upload, "Upload")

        # ----------------------------
        # Foglio Answers
        # ----------------------------
        ws_answers = wb.create_sheet("Answers", 1)  # Database_model, Answers, Examples
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
            p_label = p.id
            for q in qs_by_param.get(p.id, []):
                a = ans_by_qid.get(q.id)
                param_value = (
                    value_eval_by_pid.get(q.parameter_id)
                    or value_orig_by_pid.get(q.parameter_id)
                    or ""
                )

                if a:
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
                        _pretty_qc_from_status(getattr(a, "status", None)),
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
                        param_value,
                        "",
                        "",
                    ])
        _style_table(ws_answers, "Answers")

    suffix = "full" if is_admin else "examples"
    return wb, suffix




@login_required
def language_export_xlsx(request, lang_id: str):
    lang = get_object_or_404(Language, pk=lang_id)
    if not _check_language_access(request.user, lang):
        raise Http404("Language not found")

    wb, suffix = _build_language_workbook(lang, request.user)

    ts = now().strftime("%Y%m%d")
    filename = f"PCM_{lang.id}_{suffix}_{ts}.xlsx"
    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp



@login_required
def language_export_all_zip(request):
    """
    ADMIN: esporta TUTTE le lingue in un unico ZIP.
    Dentro lo ZIP: un .xlsx per lingua, con la stessa struttura
    di language_export_xlsx (Database_model + Answers + Examples per admin).
    """
    if not _is_admin(request.user):
        messages.error(request, _t("You are not allowed to perform this action."))
        return redirect("language_list")

    # Lingue in ordine di position/id (come in language_list)
    langs = (
        Language.objects
        .all()
        .order_by("position", "id")
    )

    zip_buffer = io.BytesIO()
    ts = now().strftime("%Y%m%d")

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for lang in langs:
            wb, suffix = _build_language_workbook(lang, request.user)

            # serializza il singolo workbook in memoria
            xlsx_io = io.BytesIO()
            wb.save(xlsx_io)
            xlsx_io.seek(0)

            inner_name = f"PCM_{lang.id}_{suffix}_{ts}.xlsx"
            zf.writestr(inner_name, xlsx_io.getvalue())

    zip_buffer.seek(0)
    zip_filename = f"PCM_languages_full_{ts}.zip"

    resp = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
    return resp
