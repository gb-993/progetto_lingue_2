from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, Count, Sum, Case, When, IntegerField

from core.models import ParameterDef
from .forms import ParameterForm, QuestionFormSet


@login_required
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
@transaction.atomic
def parameter_add(request):
    if request.method == "POST":
        form = ParameterForm(request.POST)
        if form.is_valid():
            param = form.save()
            formset = QuestionFormSet(request.POST, instance=param)
            if formset.is_valid():
                formset.save()
                return redirect(reverse("parameter_list"))
            else:
                from django.contrib import messages
                messages.error(request, "Errore nelle domande: controlla i campi evidenziati.")
                return render(request, "parameters/edit.html", {"param": param, "form": form, "q_formset": formset})
        else:
            from django.contrib import messages
            messages.error(request, "Errore nel parametro: controlla i campi evidenziati.")
            formset = QuestionFormSet()
            return render(request, "parameters/edit.html", {"param": None, "form": form, "q_formset": formset})

    form = ParameterForm()
    formset = QuestionFormSet()
    return render(request, "parameters/edit.html", {"param": None, "form": form, "q_formset": formset})


@login_required
@transaction.atomic
def parameter_edit(request, param_id):
    param = get_object_or_404(ParameterDef, pk=param_id)
    if request.method == "POST":
        form = ParameterForm(request.POST, instance=param)
        formset = QuestionFormSet(request.POST, instance=param)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect(reverse("parameter_list"))
        else:
            from django.contrib import messages
            messages.error(request, "Errore di validazione: controlla i campi evidenziati.")
            return render(request, "parameters/edit.html", {"param": param, "form": form, "q_formset": formset})

    form = ParameterForm(instance=param)
    formset = QuestionFormSet(instance=param)
    return render(request, "parameters/edit.html", {"param": param, "form": form, "q_formset": formset})