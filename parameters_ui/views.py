from __future__ import annotations

import re
from typing import List, Tuple
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from core.models import ParameterDef, Question , ParameterChangeLog 
from .forms import ParameterForm, QuestionForm, DeactivateParameterForm
from django.db.models import Q, Count, Sum, Case, When, IntegerField
from django.contrib.auth import get_user_model

# -------------------------------
# Utilità / Policy
# -------------------------------

def _is_admin(user) -> bool:
    # Semplice guard: staff o role=admin
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


# -------------------------------
# Views principali
# -------------------------------

@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET"])
def parameter_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = ParameterDef.objects.order_by("position")
    if q:
        qs = qs.filter(
            Q(id__icontains=q)
            | Q(name__icontains=q)
            | Q(short_description__icontains=q)
            | Q(implicational_condition__icontains=q)
        )
    qs = qs.annotate(
        questions_count=Count("questions", distinct=True),
        stop_count=Sum(
            Case(
                When(questions__is_stop_question=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        ),
    )
    return render(request, "parameters/list.html", {"parameters": qs})



@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def parameter_add(request):
    if request.method == "POST":
        form = ParameterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Parametro creato.")
            return redirect("parameter_list")
    else:
        form = ParameterForm()
    return render(request, "parameters/edit.html", {
        "form": form,
        "is_create": True,
        "can_deactivate": False,   # in create non ha senso
        "where_used": [],          # idem
        "deactivate_form": None,
    })

@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def parameter_edit(request, param_id: str):
    """
    Edit a parameter + compact list of its questions.
    Questions are managed via dedicated CRUD pages.
    """
    param = get_object_or_404(ParameterDef, pk=param_id)

    # Who references this parameter?
    where_used = find_where_used(param.id)
    can_deactivate = bool(param.is_active and len(where_used) == 0)

    if request.method == "POST":
        form = ParameterForm(request.POST, instance=param, can_deactivate=can_deactivate)
        if form.is_valid():
            cleaned = form.cleaned_data
            old_obj = ParameterDef.objects.get(pk=param.pk)
            diff = {}
            for f, new_val in cleaned.items():
                if f in ("change_note", "id"):
                    continue
                if hasattr(old_obj, f):
                    old_val = getattr(old_obj, f, None)
                    if old_val != new_val:
                        diff[f] = {"old": old_val, "new": new_val}

            form.save()

            if diff:
                ParameterChangeLog.objects.create(
                    parameter=param,
                    recap=(cleaned.get("change_note") or "").strip(),
                    diff=diff,
                    changed_by=request.user,
                )
                messages.success(request, "Parameter updated.")
            else:
                messages.info(request, "No changes detected.")
            return redirect("parameter_edit", param_id=param.id)
        else:
            messages.error(request, "Please fix the highlighted errors.")
    else:
        form = ParameterForm(instance=param, can_deactivate=can_deactivate)

    # Questions query
    questions = (
        param.questions
        .order_by("is_stop_question", "id")
        .select_related("parameter")
        .prefetch_related("allowed_motivations")
    )
    # >>> split lists for reliable emptiness checks in the template
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
        },
    )



@login_required
@user_passes_test(_is_admin)
@require_POST
def parameter_deactivate(request, param_id: str):
    """
    Disattiva un parametro SOLO se non esistono più referenze a lui,
    richiedendo conferma password. Protezione race: lock + ricontrollo in transazione.
    """
    # Form di conferma (password + motivo)
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
            },
            status=400,
        )

    with transaction.atomic():
        # Lock del record per evitare race tra più admin
        param = ParameterDef.objects.select_for_update().get(pk=param_id)

        # Ricontrollo referenze "ora"
        refs_now = find_where_used(param.id)
        if refs_now:
            messages.error(
                request,
                "Impossibile disattivare: sono comparse nuove referenze. Ripulisci e riprova."
            )
            return redirect("parameter_edit", param_id=param.id)

        if not param.is_active:
            messages.info(request, "Il parametro è già disattivato.")
            return redirect("parameter_edit", param_id=param.id)

        # Disattiva
        param.is_active = False
        param.save(update_fields=["is_active"])

    reason = (form.cleaned_data.get("reason") or "").strip()
    messages.success(
        request,
        f"Parametro {param.id} disattivato correttamente." + (f" Motivo: {reason}" if reason else "")
    )
    return redirect("parameter_edit", param_id=param.id)

@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_add(request, param_id: str):
    """
    Crea una nuova domanda per il parametro.
    - Mostra la checkbox 'is_stop_question' SOLO qui (in creazione).
    """
    param = get_object_or_404(ParameterDef, pk=param_id)
    instance = Question(parameter=param)

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=instance)
        # In creazione, la checkbox 'is_stop_question' è presente (vedi forms.__init__)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.parameter = param
                obj.save()
                # salva anche M2M/motivations (la save del form già gestisce la tabella ponte)
                form.save_m2m()
            messages.success(request, "Domanda creata.")
            return redirect("parameter_edit", param_id=param.id)
        else:
            messages.error(request, "Correggi gli errori nella domanda.")
    else:
        form = QuestionForm(instance=instance)  # crea con checkbox visibile

    return render(
        request,
        "parameters/question_form.html",
        {"form": form, "parameter": param, "is_create": True},
    )


@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_edit(request, param_id: str, question_id: str):
    """
    Modifica una domanda esistente.
    - La checkbox 'is_stop_question' NON è mostrata (nascosta/poppata in forms.__init__).
    """
    param = get_object_or_404(ParameterDef, pk=param_id)
    question = get_object_or_404(Question, pk=question_id, parameter=param)

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, "Domanda aggiornata.")
            return redirect("parameter_edit", param_id=param.id)
        else:
            messages.error(request, "Correggi gli errori nella domanda.")
    else:
        form = QuestionForm(instance=question)

    return render(
        request,
        "parameters/question_form.html",
        {"form": form, "parameter": param, "is_create": False, "question": question},
    )


@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def question_delete(request, param_id: str, question_id: str):
    """
    Conferma/elimina una domanda.
    """
    param = get_object_or_404(ParameterDef, pk=param_id)
    question = get_object_or_404(Question, pk=question_id, parameter=param)

    if request.method == "POST":
        question.delete()
        messages.success(request, f"Domanda {question_id} eliminata.")
        return redirect("parameter_edit", param_id=param.id)

    return render(
        request,
        "parameters/question_confirm_delete.html",
        {"parameter": param, "question": question},
    )
