from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import Glossary
from .forms import GlossaryForm

def _is_admin(user):
    return user.is_authenticated and (getattr(user, 'role', '') == 'admin' or user.is_superuser)
@login_required
def glossary_list(request):
    """
    Tutti vedono la lista e possono cercare. Solo gli admin vedono bottoni Add/Edit/Delete.
    """
    q = (request.GET.get("q") or "").strip()
    qs = Glossary.objects.all().order_by("word")
    if q:
        qs = qs.filter(
            Q(word__icontains=q) |
            Q(description__icontains=q)
        )

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "page_obj": page_obj,
        "q": q,
        "is_admin": _is_admin(request.user),
    }
    return render(request, "glossary/list.html", ctx)

@login_required
@user_passes_test(_is_admin)
def glossary_add(request):
    """
    Solo admin: crea una nuova voce.
    """
    if request.method == "POST":
        form = GlossaryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Entry created successfully")
            return redirect("glossary_list")
        messages.error(request, "Correct the errors and try again.")
    else:
        form = GlossaryForm()

    return render(request, "glossary/add.html", {"form": form})

@login_required
def glossary_view(request, word):
    """
    Vista di dettaglio in sola lettura per gli user.
    Gli admin vedono anche il pulsante 'Modifica'.
    """
    obj = get_object_or_404(Glossary, word=word)
    return render(request, "glossary/view.html", {"obj": obj, "is_admin": _is_admin(request.user)})

@login_required
@user_passes_test(_is_admin)
def glossary_edit(request, word):
    """
    Solo admin: modifica voce esistente.
    """
    obj = get_object_or_404(Glossary, word=word)
    if request.method == "POST":
        form = GlossaryForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Entry updated")
            return redirect("glossary_list")
        messages.error(request, "Correct the errors and try again.")
    else:
        form = GlossaryForm(instance=obj)
    return render(request, "glossary/edit.html", {"form": form, "obj": obj})

@login_required
@user_passes_test(_is_admin)
def glossary_delete(request, word):
    """
    Solo admin: elimina (POST).
    """
    obj = get_object_or_404(Glossary, word=word)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Entry deleted")
        return redirect("glossary_list")
    return render(request, "glossary/confirm_delete.html", {"obj": obj})
