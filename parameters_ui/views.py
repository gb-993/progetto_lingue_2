from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from .forms import ParameterForm
from django.db import transaction
from django.db.models import Q, Count, Sum, Case, When, IntegerField
from core.models import ParameterDef, Question
from .forms import ParameterForm, QuestionFormSet


@login_required
def parameter_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = ParameterDef.objects.order_by("position")
    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(name__icontains=q) |
            Q(short_description__icontains=q) |
            Q(implicational_condition__icontains=q)
        )
        # (Punto 5) Annotazioni per #Q e #Stop che il tuo template usa.
    qs = qs.annotate(
        questions_count=Count("questions", distinct=True),
        stop_count=Sum(
            Case(When(questions__is_stop_question=True, then=1), default=0, output_field=IntegerField())
        )
    )
    return render(request, "parameters/list.html", {"parameters": qs})




@login_required
@transaction.atomic
def parameter_edit(request, param_id):
    param = get_object_or_404(ParameterDef, pk=param_id)

    if request.method == "POST":
        form = ParameterForm(request.POST, instance=param)
        formset = QuestionFormSet(request.POST, instance=param)
        if form.is_valid() and formset.is_valid():
            form.save()          # shift position gestito in model.save()
            formset.save()       # ogni Question salva anche le sue motivazioni
            return redirect(reverse("parameter_list"))
    else:
        form = ParameterForm(instance=param)
        formset = QuestionFormSet(instance=param)

    return render(request, "parameters/edit.html", {"param": param, "form": form, "q_formset": formset})

@login_required
@transaction.atomic
def parameter_add(request):
    param = None
    if request.method == "POST":
        form = ParameterForm(request.POST)
        formset = QuestionFormSet(request.POST, instance=param)  # instance=None in create
        if form.is_valid() and formset.is_valid():
            # Salva prima il parametro (così le Question hanno FK valida)
            param = form.save()
            formset.instance = param
            formset.save()  # ciascun form Question salva anche le motivazioni
            return redirect(reverse("parameter_list"))
    else:
        form = ParameterForm()
        formset = QuestionFormSet(instance=param)

    return render(request, "parameters/edit.html", {"param": param, "form": form, "q_formset": formset})

