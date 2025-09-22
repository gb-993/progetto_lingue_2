from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.urls import reverse

from core.models import ParameterDef
from .forms import ParameterForm


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
            form.save()  # lo shift di position è gestito dal model.save()
            return redirect(reverse("parameter_list"))
    else:
        form = ParameterForm(instance=param)
    return render(request, "parameters/edit.html", {"param": param, "form": form})


@login_required
def parameter_add(request):
    if request.method == "POST":
        form = ParameterForm(request.POST)
        if form.is_valid():
            form.save()  # se position manca o è <1, il model.save() la normalizza
            return redirect(reverse("parameter_list"))
    else:
        form = ParameterForm()
    return render(request, "parameters/edit.html", {"form": form, "param": None})
