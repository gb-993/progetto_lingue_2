from __future__ import annotations

import re
from typing import List, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from core.models import ParameterDef, Question  # aggiungi altri import se servono nei tuoi formset
from .forms import ParameterForm, QuestionFormSet, DeactivateParameterForm
from django.db.models import Q, Count, Sum, Case, When, IntegerField


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
    - Mostra/edita i dati del parametro
    - Calcola la lista di 'where used' (chi mi cita)
    - Se ci sono referenze e il parametro è attivo -> il toggle is_active è disabilitato (client) e c'è enforcement server-side
    - Se NON ci sono referenze -> mostra form di disattivazione con password
    """
    param = get_object_or_404(ParameterDef, pk=param_id)

    # Calcola referenze: chi cita questo parametro
    where_used = find_where_used(param.id)
    can_deactivate = bool(param.is_active and len(where_used) == 0)

    if request.method == "POST":
        form = ParameterForm(request.POST, instance=param)
        if form.is_valid():
            # Enforcement server-side: se si tenta di impostare is_active=False quando NON consentito, blocca
            cleaned = form.cleaned_data
            wants_inactive = (cleaned.get("is_active") is False)
            if wants_inactive and not can_deactivate:
                messages.error(request, "Non puoi disattivare questo parametro: esistono ancora referenze.")
                # Non salviamo; ricarichiamo la pagina senza cambiare stato
            else:
                form.save()
                messages.success(request, "Parametro aggiornato.")
                return redirect("parameter_edit", param_id=param.id)
    else:
        form = ParameterForm(instance=param)

    deactivate_form = DeactivateParameterForm(request=None) if can_deactivate else None

    return render(request, "parameters/edit.html", {
        "form": form,
        "is_create": False,
        "parameter": param,
        "can_deactivate": can_deactivate,
        "where_used": where_used,
        "deactivate_form": deactivate_form,
    })


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
