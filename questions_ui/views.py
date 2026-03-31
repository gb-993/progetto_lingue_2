from typing import Any

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from core.models import Question


def _is_admin(user: Any) -> bool:
    """Return whether the given user should be treated as administrator.

    Args:
        user: User-like object attached to the current request.

    Returns:
        ``True`` when the user is authenticated and is staff or has role
        ``admin``; otherwise ``False``.
    """
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


@login_required
@user_passes_test(_is_admin)
def question_list(request: HttpRequest) -> HttpResponse:
    """Render the admin-only list of questions with optional search filter.

    Args:
        request: Current authenticated admin request.

    Returns:
        Rendered questions list page with filtered queryset and search term.
    """

    query = request.GET.get("q", "").strip()

    # Base query con ottimizzazione per evitare N+1 queries
    qs = Question.objects.select_related('parameter').order_by('parameter__position', 'id')

    # Filtraggio se presente una stringa di ricerca
    if query:
        qs = qs.filter(
            Q(text__icontains=query) |
            Q(id__icontains=query) |
            Q(parameter__id__icontains=query)
        )

    return render(request, "questions/list.html", {
        "questions": qs,
        "q": query  # Passato per mantenere il testo nella barra di ricerca
    })