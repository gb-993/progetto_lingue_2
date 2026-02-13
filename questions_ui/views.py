from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from core.models import Question


def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


@login_required
@user_passes_test(_is_admin)
def question_list(request):

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