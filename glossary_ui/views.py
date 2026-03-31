from typing import Any

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse

from core.models import Glossary
from .forms import GlossaryForm

def _is_admin(user: Any) -> bool:
    """Check whether the current user has administrative permissions.

    Args:
        user: User-like object attached to the request.

    Returns:
        ``True`` when the user is authenticated and has role ``admin`` or is
        superuser, otherwise ``False``.
    """
    return user.is_authenticated and (getattr(user, 'role', '') == 'admin' or user.is_superuser)


@login_required
def glossary_list(request: HttpRequest) -> HttpResponse:
    """Show the glossary list with optional search and pagination.

    All authenticated users can access this page. Admin-related actions are
    enabled in the template through the ``is_admin`` flag.

    Args:
        request: Current authenticated HTTP request.

    Returns:
        Rendered glossary list page with paginated entries.
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
def glossary_add(request: HttpRequest) -> HttpResponse:
    """Create a new glossary entry.

    Access is restricted to administrators.

    Args:
        request: Current authenticated admin request.

    Returns:
        Form page on GET/validation error, or redirect to ``glossary_list``
        after successful creation.
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
def glossary_view(request: HttpRequest, word: str) -> HttpResponse:
    """Display a read-only detail page for a glossary entry.

    Args:
        request: Current authenticated HTTP request.
        word: Primary lookup key for the glossary entry.

    Returns:
        Rendered detail page for the requested entry.
    """
    obj = get_object_or_404(Glossary, word=word)
    return render(request, "glossary/view.html", {"obj": obj, "is_admin": _is_admin(request.user)})

@login_required
@user_passes_test(_is_admin)
def glossary_edit(request: HttpRequest, word: str) -> HttpResponse:
    """Edit an existing glossary entry.

    Access is restricted to administrators.

    Args:
        request: Current authenticated admin request.
        word: Primary lookup key for the glossary entry to edit.

    Returns:
        Edit form page on GET/validation error, or redirect to
        ``glossary_list`` after successful update.
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
def glossary_delete(request: HttpRequest, word: str) -> HttpResponse:
    """Delete a glossary entry after confirmation.

    Access is restricted to administrators. Deletion is executed only for POST
    requests.

    Args:
        request: Current authenticated admin request.
        word: Primary lookup key for the glossary entry to delete.

    Returns:
        Confirmation page on GET, or redirect to ``glossary_list`` after
        successful deletion.
    """
    obj = get_object_or_404(Glossary, word=word)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Entry deleted")
        return redirect("glossary_list")
    return render(request, "glossary/confirm_delete.html", {"obj": obj})
