from __future__ import annotations

import re
from typing import List, Tuple
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models import Q, Count, Sum, Case, When, IntegerField

from core.models import (
    ParameterDef,
    Question,
    ParameterChangeLog,
    Language,
    ParameterReviewFlag,
    Answer,
    Example,
    AnswerMotivation,
    QuestionAllowedMotivation,
    Motivation,
    ParamSchema,
    ParamType,
    ParamLevelOfComparison,

)

from .forms import (
    ParameterForm,
    QuestionForm,
    DeactivateParameterForm,
)


# -------------------------------
# Utilità / Policy
# -------------------------------

def _is_admin(user) -> bool:
    
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))

# token tipo +FGM, -SCO, 0ABC: segno e ID senza spazi
TOKEN_RE = re.compile(r'([+\-0])([A-Z][A-Z0-9]{0,9})')

def extract_tokens(expression: str) -> List[Tuple[str, str]]:
    """
    Estrae i token (sign, ID) da una implicational_condition.
    Esempi: +FGM, -SCO, 0ABC -> [('+','FGM'),('-','SCO'),('0','ABC')]
    """
    expr = (expression or "").strip().upper()
    return TOKEN_RE.findall(expr)

def find_where_used(param_id: str) -> List[Tuple[ParameterDef, str]]:
    """
    Ritorna la lista dei parametri (target) che citano 'param_id' nella loro implicational_condition.
    Ogni item: (ParameterDef target, condizione_raw)
    """
    param_id = (param_id or "").upper().strip()
    results: List[Tuple[ParameterDef, str]] = []
    # Scansiona tutti tranne se stesso; ignora vuote
    for target in ParameterDef.objects.exclude(id=param_id).only("id", "name", "implicational_condition", "position"):
        cond = (target.implicational_condition or "").strip()
        if not cond:
            continue
        for sign, tok in extract_tokens(cond):
            if tok == param_id:
                results.append((target, cond))
                break
    return results

def _to_jsonable(value):
    """
    Converte valori (inclusi Model instance) in strutture JSON-safe.
    - Model -> {"id": pk, "label": str(obj)}
    - liste/tuple/set/dict -> ricorsivo
    - tipi base -> come sono
    """
    from django.db.models import Model

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Model):
        return {"id": getattr(value, "pk", None), "label": str(value)}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return str(value)
# -------------------------------
# Views principali
# -------------------------------
@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET"])
def parameter_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = (
        ParameterDef.objects
        .order_by("position")
        
    )
    if q:
        qs = qs.filter(
            Q(id__icontains=q)
            | Q(name__icontains=q)
            | Q(short_description__icontains=q)
            | Q(long_description__icontains=q)
            | Q(description_of_the_implicational_condition__icontains=q)
            | Q(implicational_condition__icontains=q)
            | Q(schema__icontains=q)
            | Q(param_type__icontains=q)
            | Q(level_of_comparison__icontains=q)
        )
    qs = qs.annotate(
        questions_count=Count("questions", filter=Q(questions__is_stop_question=False), distinct=True),
        stop_count=Count("questions", filter=Q(questions__is_stop_question=True), distinct=True),
    )

    
    return render(request, "parameters/list.html", {"parameters": qs, "q": q})

@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def parameter_add(request):
    if request.method == "POST":
        form = ParameterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Parameter added successfully.")
            return redirect("parameter_list")
    else:
        form = ParameterForm()

    schema_options = list(ParamSchema.objects.order_by("label").values_list("label", flat=True))
    type_options   = list(ParamType.objects.order_by("label").values_list("label", flat=True))
    level_options = list(ParamLevelOfComparison.objects.order_by("label").values_list("label", flat=True))

    return render(
        request,
        "parameters/edit.html",
        {
            "form": form,
            "is_create": True,
            "can_deactivate": False,
            "where_used": [],
            "deactivate_form": None,
            "schema_options": schema_options,
            "type_options": type_options,
        },
    )



@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def parameter_edit(request, param_id: str):
    """
    Edit a parameter + compact list of its questions.
    - Richiede change_note SE ci sono modifiche al parametro (logica in form.clean())
      O se ci sono state modifiche esterne (domande / motivations) nel flusso corrente.
    - Serializza i campi FK nel diff per il JSONField (id+label).
    """
    param = get_object_or_404(ParameterDef, pk=param_id)

    where_used = find_where_used(param.id)
    can_deactivate = bool(param.is_active and len(where_used) == 0)

    if request.method == "POST":
        form = ParameterForm(request.POST, instance=param, can_deactivate=can_deactivate)

        had_external_changes = request.POST.get("had_external_changes") == "1"

        if form.is_valid():
            old_obj = ParameterDef.objects.get(pk=param.pk)

            changed_fields = [f for f in form.changed_data if f not in ("change_note", "id")]
            diff = {}
            for f in changed_fields:
                old_val = getattr(old_obj, f, None)
                new_val = form.cleaned_data.get(f)
                if old_val != new_val:
                    diff[f] = {"old": _to_jsonable(old_val), "new": _to_jsonable(new_val)}

            note_val = (form.cleaned_data.get("change_note") or "").strip()
            if had_external_changes and not note_val:
                form.add_error(
                    "change_note",
                    "Insert recap of changes made to this parameter, its questions, or motivations."
                )
                messages.error(request, "Please add a recap of the external changes.")
            else:
                param = form.save()


                if diff:
                    ParameterChangeLog.objects.create(
                        parameter=param,
                        recap=note_val,
                        diff=diff,
                        changed_by=request.user,
                    )
                    messages.success(request, "Parameter updated.")
                else:

                    if had_external_changes and note_val:
                        ParameterChangeLog.objects.create(
                            parameter=param,
                            recap=note_val,
                            diff={"_external": "Questions/motivations changed"},
                            changed_by=request.user,
                        )
                        messages.success(request, "Parameter notes saved.")
                    else:
                        messages.info(request, "No changes detected.")
                return redirect("parameter_edit", param_id=param.id)

        else:
            messages.error(request, "Please add a recap of the external changes.")

        questions = (
            param.questions
            .order_by("is_stop_question", "id")
            .select_related("parameter")
            .prefetch_related("allowed_motivations")
        )
        questions_normal = [q for q in questions if not q.is_stop_question]
        questions_stop = [q for q in questions if q.is_stop_question]

        deactivate_form = DeactivateParameterForm(request=None) if can_deactivate else None

        return render(
            request,
            "parameters/edit.html",
            {
                "form": form,
                "is_create": False,
                "parameter": param,
                "can_deactivate": can_deactivate,
                "where_used": where_used,
                "deactivate_form": deactivate_form,
                "questions": questions,
                "questions_normal": questions_normal,
                "questions_stop": questions_stop,
                "external_dirty": had_external_changes,
            },
            status=400,
        )

    else:
        form = ParameterForm(instance=param, can_deactivate=can_deactivate)

        q_changed_flag = request.GET.get("q_changed") == "1"
        external_dirty = q_changed_flag

        questions = (
            param.questions
            .order_by("is_stop_question", "id")
            .select_related("parameter")
            .prefetch_related("allowed_motivations")
        )
        questions_normal = [q for q in questions if not q.is_stop_question]
        questions_stop = [q for q in questions if q.is_stop_question]

        deactivate_form = DeactivateParameterForm(request=None) if can_deactivate else None

        return render(
            request,
            "parameters/edit.html",
            {
                "form": form,
                "is_create": False,
                "parameter": param,
                "can_deactivate": can_deactivate,
                "where_used": where_used,
                "deactivate_form": deactivate_form,
                "questions": questions,
                "questions_normal": questions_normal,
                "questions_stop": questions_stop,
                "external_dirty": external_dirty,
            },
        )



@login_required
@user_passes_test(_is_admin)
@require_POST
def parameter_deactivate(request, param_id: str):

    form = DeactivateParameterForm(request.POST, request=request)
    if not form.is_valid():
        param = get_object_or_404(ParameterDef, pk=param_id)
        where_used = find_where_used(param.id)
        can_deactivate = bool(param.is_active and len(where_used) == 0)
        return render(
            request,
            "parameters/edit.html",
            {
                "form": ParameterForm(instance=param),
                "is_create": False,
                "parameter": param,
                "can_deactivate": can_deactivate,
                "where_used": where_used,
                "deactivate_form": form,
                "schema_options": list(ParamSchema.objects.order_by("label").values_list("label", flat=True)),
                "type_options": list(ParamType.objects.order_by("label").values_list("label", flat=True)),
            },
            status=400,
        )



    with transaction.atomic():
        param = ParameterDef.objects.select_for_update().get(pk=param_id)

        refs_now = find_where_used(param.id)
        if refs_now:
            messages.error(
                request,
                "Unable to deactivate: new implicational conditions mentioning this parameter have appeared. Clean up and try again"
            )
            return redirect("parameter_edit", param_id=param.id)

        if not param.is_active:
            messages.info(request, "The parameter is already deactivated.")
            return redirect("parameter_edit", param_id=param.id)

        param.is_active = False
        param.save(update_fields=["is_active"])

    reason = (form.cleaned_data.get("reason") or "").strip()
    messages.success(
        request,
        f"Parameter {param.id} successfully deactivated." + (f" Reason: {reason}" if reason else "")
    )
    return redirect("parameter_edit", param_id=param.id)



# --- Helpers per clonare domande + risposte/esempi -------------------------

def _suggest_question_id_for_target(src_q: Question, target_param: ParameterDef) -> str:
    """
    Prova a costruire un nuovo id coerente col parametro di destinazione.
    Esempio:
      src_q.id = 'FGM_Qc', src_q.parameter_id = 'FGM', target_param.id = 'FGA'
      -> 'FGA_Qc'
    Se il pattern non è riconoscibile, usa 'FGA_<oldid>'.
    Se l'id esiste già, aggiunge un suffisso numerico (_copy2, _copy3, ...).
    """
    src_id = (src_q.id or "").strip()
    src_param_id = (src_q.parameter_id or "").strip()
    dst_id = (target_param.id or "").strip()

    if src_id.startswith(src_param_id + "_"):
        suffix = src_id[len(src_param_id):]  # include underscore + resto
        base = dst_id + suffix
    else:
        base = f"{dst_id}_{src_id}"

    candidate = base
    counter = 2
    while Question.objects.filter(pk=candidate).exists():
        candidate = f"{base}_copy{counter}"
        counter += 1
    return candidate


def _clone_question_with_answers(
    src_q: Question,
    target_param: ParameterDef,
    new_id: str,
) -> tuple[Question, dict]:
    """
    Clona:
      - la Question (con nuovo id e nuovo parametro)
      - i QuestionAllowedMotivation
      - le Answer per ogni lingua (solo contenuto, NON lo status)
      - gli AnswerMotivation
      - gli Example
    Ritorna (new_question, stats_dict).
    """
    stats = {"answers": 0, "examples": 0, "answer_motivations": 0, "allowed_motivations": 0}

    with transaction.atomic():
        # 1) nuova question
        new_q = Question.objects.create(
            id=new_id,
            parameter=target_param,
            text=src_q.text,
            example_yes=src_q.example_yes,
            instruction_yes=src_q.instruction_yes,
            instruction_no=src_q.instruction_no,
            instruction=src_q.instruction,
            template_type=src_q.template_type,
            is_stop_question=src_q.is_stop_question,
            help_info=src_q.help_info,
        )

        # 2) allowed motivations
        qam_links = list(
            QuestionAllowedMotivation.objects.filter(question=src_q).values(
                "motivation_id", "position"
            )
        )
        if qam_links:
            QuestionAllowedMotivation.objects.bulk_create(
                [
                    QuestionAllowedMotivation(
                        question=new_q,
                        motivation_id=row["motivation_id"],
                        position=row["position"],
                    )
                    for row in qam_links
                ],
                ignore_conflicts=True,
            )
            stats["allowed_motivations"] = len(qam_links)

        # 3) answers + motivations + examples
        answers = (
            Answer.objects
            .filter(question=src_q)
            .prefetch_related("answer_motivations__motivation", "examples")
        )

        for src_ans in answers:
            # nuove Answer: status/modifiable lasciati ai default (pending/editable)
            new_ans = Answer.objects.create(
                language=src_ans.language,
                question=new_q,
                response_text=src_ans.response_text,
                comments=src_ans.comments,
            )
            stats["answers"] += 1

            # AnswerMotivation
            am_list = list(src_ans.answer_motivations.all())
            if am_list:
                AnswerMotivation.objects.bulk_create(
                    [
                        AnswerMotivation(
                            answer=new_ans,
                            motivation=am.motivation,
                        )
                        for am in am_list
                    ],
                    ignore_conflicts=True,
                )
                stats["answer_motivations"] += len(am_list)

            # Examples
            ex_list = list(src_ans.examples.all())
            if ex_list:
                Example.objects.bulk_create(
                    [
                        Example(
                            answer=new_ans,
                            number=ex.number,
                            textarea=ex.textarea,
                            gloss=ex.gloss,
                            translation=ex.translation,
                            transliteration=ex.transliteration,
                            reference=ex.reference,
                        )
                        for ex in ex_list
                    ]
                )
                stats["examples"] += len(ex_list)

    return new_q, stats




@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_add(request, param_id: str):

    param = get_object_or_404(ParameterDef, pk=param_id)
    instance = Question(parameter=param)

    if request.method == "POST":
        q_form = QuestionForm(request.POST, instance=instance)

        if q_form.is_valid():
            with transaction.atomic():
                obj = q_form.save(commit=False)
                obj.parameter = param
                obj.save()
                q_form.save_m2m()

            messages.success(request, "Question created.")
            return redirect(f"{reverse('parameter_edit', args=[param.id])}?q_changed=1")
        else:
            messages.error(request, "Please add a recap of the external changes.")
            return render(
                request,
                "parameters/question_form.html",
                {
                    "form": q_form,
                    "parameter": param,
                    "is_create": True,
                },
            )

    else:
        q_form = QuestionForm(instance=instance)
        return render(
            request,
            "parameters/question_form.html",
            {
                "form": q_form,
                "parameter": param,
                "is_create": True,
            },
        )




@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_edit(request, param_id: str, question_id: str):

    param = get_object_or_404(ParameterDef, pk=param_id)
    question = get_object_or_404(Question, pk=question_id, parameter=param)

    if request.method == "POST":
        q_form = QuestionForm(request.POST, instance=question)

        if q_form.is_valid():
            q_form.save()
            messages.success(request, "Question updated.")

            # Se proveniamo dalla lista globale delle domande, torniamo lì
            if request.GET.get('from') == 'questions':
                return redirect('questions_list')

            return redirect(f"{reverse('parameter_edit', args=[param.id])}?q_changed=1")
        else:
            messages.error(request, "Correggi gli errori nella domanda.")
            return render(
                request,
                "parameters/question_form.html",
                {
                    "form": q_form,
                    "parameter": param,
                    "is_create": False,
                    "question": question,
                },
            )

    else:
        q_form = QuestionForm(instance=question)
        return render(
            request,
            "parameters/question_form.html",
            {
                "form": q_form,
                "parameter": param,
                "is_create": False,
                "question": question,
            },
        )





from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (
    ParameterDef,
    Question,
    Answer,
    Example,
    AnswerMotivation,
    QuestionAllowedMotivation,
    ParamLevelOfComparison,
)

@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_delete(request, param_id: str, question_id: str):
    param = get_object_or_404(ParameterDef, pk=param_id)
    question = get_object_or_404(Question, pk=question_id, parameter=param)

    answers_qs = Answer.objects.filter(question=question)
    examples_qs = Example.objects.filter(answer__question=question)
    amots_qs   = AnswerMotivation.objects.filter(answer__question=question)
    qam_qs     = QuestionAllowedMotivation.objects.filter(question=question)

    counts = {
        "answers": answers_qs.count(),
        "examples": examples_qs.count(),
        "answer_motivations": amots_qs.count(),
        "allowed_motivations": qam_qs.count(),
    }

    if request.method == "GET":
        return render(
            request,
            "parameters/question_confirm_delete.html",
            {
                "parameter": param,
                "question": question,
                "counts": counts,
                "can_force": (counts["answers"] > 0 or counts["examples"] > 0 or counts["answer_motivations"] > 0),
            },
        )

    force = request.POST.get("force") == "1"

    if (counts["answers"] > 0 or counts["examples"] > 0 or counts["answer_motivations"] > 0) and not force:
        messages.error(
            request,
            (
                f"Unable to delete: found {counts['answers']} answers, "
                f"{counts['examples']} examples, and {counts['answer_motivations']} motivations. "
                "Check 'Delete related data as well' to force deletion."
            ),
        )
        return render(
            request,
            "parameters/question_confirm_delete.html",
            {
                "parameter": param,
                "question": question,
                "counts": counts,
                "can_force": True,
            },
            status=409,
        )

    with transaction.atomic():
        amots_qs.delete()
        examples_qs.delete()
        answers_qs.delete()
        qam_qs.delete()
        question.delete()

    messages.success(request, f"Question {question_id} deleted.")

    # Se proveniamo dalla lista globale delle domande, torniamo lì
    if request.GET.get('from') == 'questions':
        return redirect('questions_list')

    return redirect(f"{reverse('parameter_edit', args=[param.id])}?q_changed=1")



@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_clone(request, param_id: str):
    """
    Admin: importa una question esistente (con risposte + esempi)
    dentro il parametro di destinazione `param_id`.

    POST fields:
      - source_question_id: id della question sorgente (es. FGM_Qc)
      - new_id (opzionale): nuovo id per la question clonata; se vuoto lo proponiamo noi.
    """
    target_param = get_object_or_404(ParameterDef, pk=param_id)

    if request.method == "POST":
        src_qid = (request.POST.get("source_question_id") or "").strip()
        new_id = (request.POST.get("new_id") or "").strip()

        if not src_qid:
            messages.error(request, "Source question ID is required.")
            return render(
                request,
                "parameters/question_clone.html",
                {
                    "parameter": target_param,
                    "source_question_id": src_qid,
                    "new_id": new_id,
                },
                status=400,
            )

        try:
            src_q = Question.objects.select_related("parameter").get(pk=src_qid)
        except Question.DoesNotExist:
            messages.error(request, f"Question '{src_qid}' not found.")
            return render(
                request,
                "parameters/question_clone.html",
                {
                    "parameter": target_param,
                    "source_question_id": src_qid,
                    "new_id": new_id,
                },
                status=404,
            )

        # se new_id vuoto, lo suggeriamo in base al parametro di destinazione
        if not new_id:
            new_id = _suggest_question_id_for_target(src_q, target_param)

        # unicità id
        if Question.objects.filter(pk=new_id).exists():
            messages.error(
                request,
                f"A question with id '{new_id}' already exists. Please choose another id."
            )
            return render(
                request,
                "parameters/question_clone.html",
                {
                    "parameter": target_param,
                    "source_question_id": src_qid,
                    "new_id": new_id,
                },
                status=400,
            )

        # clonazione
        new_q, stats = _clone_question_with_answers(src_q, target_param, new_id)

        messages.success(
            request,
            (
                f"Question {src_q.id} copied to parameter {target_param.id} as {new_q.id}. "
                f"Imported {stats['answers']} answers and {stats['examples']} examples."
            ),
        )
        # q_changed=1 così il parametro risulta 'sporco' per il log
        return redirect(f"{reverse('parameter_edit', args=[target_param.id])}?q_changed=1")

    # GET: mostra form vuoto
    return render(
        request,
        "parameters/question_clone.html",
        {
            "parameter": target_param,
            "source_question_id": "",
            "new_id": "",
        },
    )




@login_required
@require_http_methods(["GET"])
def review_flags_list(request, lang_id: str):

    lang = get_object_or_404(Language, pk=lang_id)
    qs = ParameterReviewFlag.objects.filter(language=lang, user=request.user, flag=True).values_list("parameter_id", flat=True)
    return JsonResponse({"flags": list(qs)})


@login_required
@require_POST
def toggle_review_flag(request, lang_id: str, param_id: str):

    lang = get_object_or_404(Language, pk=lang_id)
    param = get_object_or_404(ParameterDef, pk=param_id)
    flag_val = request.POST.get("flag")
    if flag_val not in ("0", "1"):
        return HttpResponseBadRequest("flag must be 0 or 1")

    obj, _ = ParameterReviewFlag.objects.get_or_create(language=lang, parameter=param, user=request.user)
    obj.flag = (flag_val == "1")
    obj.save(update_fields=["flag", "updated_at"])
    return JsonResponse({"ok": True, "flag": obj.flag})



@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def lookups_manage(request):

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "add_schema":
                ParamSchema.objects.create(
                    label=(request.POST.get("label") or "").strip(),
                )
                messages.success(request, "Schema added.")
                return redirect("param_lookups_manage")

            if action == "del_schema":
                pk = request.POST.get("id")
                ParamSchema.objects.filter(pk=pk).delete()
                messages.success(request, "Schema deleted.")
                return redirect("param_lookups_manage")

            if action == "add_type":
                ParamType.objects.create(
                    label=(request.POST.get("label") or "").strip(),
                )
                messages.success(request, "Type added.")
                return redirect("param_lookups_manage")

            if action == "del_type":
                pk = request.POST.get("id")
                ParamType.objects.filter(pk=pk).delete()
                messages.success(request, "Type deleted.")
                return redirect("param_lookups_manage")

            if action == "add_level":
                ParamLevelOfComparison.objects.create(
                    label=(request.POST.get("label") or "").strip(),
                )
                messages.success(request, "Level added.")
                return redirect("param_lookups_manage")

            if action == "del_level":
                pk = request.POST.get("id")
                ParamLevelOfComparison.objects.filter(pk=pk).delete()
                messages.success(request, "Level deleted.")
                return redirect("param_lookups_manage")


            messages.error(request, "Unknown action.")
        except Exception as e:
            messages.error(request, f"Operation failed: {e}")

    schemas = ParamSchema.objects.order_by("label")
    types = ParamType.objects.order_by("label")
    levels = ParamLevelOfComparison.objects.order_by("label")

    return render(request, "parameters/lookups.html", {
        "schemas": schemas,
        "types": types,
        "levels": levels
    })



@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def motivations_manage(request):

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "add_motivation":
                Motivation.objects.create(
                    code=(request.POST.get("code") or "").strip(),
                    label=(request.POST.get("label") or "").strip(),
                )
                messages.success(request, "Motivation added.")
                return redirect("motivations_manage")

            if action == "del_motivation":
                pk = request.POST.get("id")

                try:
                    Motivation.objects.filter(pk=pk).delete()
                    messages.success(request, "Motivation deleted.")
                except Exception as e:
                    messages.error(request, f"Cannot delete motivation: {e}")
                return redirect("motivations_manage")

            messages.error(request, "Unknown action.")
        except Exception as e:
            messages.error(request, f"Operation failed: {e}")

    motivations = Motivation.objects.order_by("code")
    return render(request, "parameters/motivations.html", {"motivations": motivations})
