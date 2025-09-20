from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from core.models import ParameterDef
from .forms import ParameterForm
from django.urls import reverse


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
    return render(request, "parameters/list.html", {"parameters": qs})

@login_required
def parameter_edit(request, param_id):


    param = get_object_or_404(ParameterDef, pk=param_id)

    if request.method == "POST":
        form = ParameterForm(request.POST, instance=param)
        if form.is_valid():
            form.save()
            return redirect(reverse("parameter_list"))
    else:
        form = ParameterForm(instance=param)

    ctx = {
        "param": param,   # per mostrare id/label read-only nel template
        "form": form,
        # "questions": ..., "motivations": ..., "selected_motivation_ids": ...
    }
    return render(request, "parameters/edit.html", ctx)

@login_required
def parameter_add(request):
    if request.method == "POST":
        form = ParameterForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            # Se l'ID è manuale (stringa tipo 'FGM'), devi prenderlo da un input separato:
            # obj.id = (request.POST.get("id") or "").strip()
            obj.save()
            return redirect(reverse("parameter_list"))
    else:
        form = ParameterForm()

    return render(request, "parameters/edit.html", {"form": form, "param": None})
