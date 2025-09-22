from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

from core.models import User
try:
    from core.models import Language
    HAS_LANGUAGE = True
except Exception:
    Language = None
    HAS_LANGUAGE = False

from .forms import AccountForm


def _is_admin(user: User) -> bool:
    # consenti solo a admin/staff di gestire gli account
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


@login_required
def dashboard(request):
    is_admin = (
        request.user.is_staff
        or request.user.is_superuser
        or getattr(request.user, "role", "") == "admin"
    )
    return render(request, "accounts/dashboard.html", {"is_admin": is_admin})


@login_required
@user_passes_test(_is_admin)
def accounts_list(request):
    """
    Lista con filtro 'q' (email/nome/cognome), split per ruolo.
    Accessibile solo ad admin/staff.
    """
    q = (request.GET.get("q") or "").strip()

    qs = User.objects.order_by("surname", "name", "email")
    if q:
        qs = qs.filter(
            Q(email__icontains=q) |
            Q(name__icontains=q) |
            Q(surname__icontains=q)
        )

    admins = qs.filter(role="admin")
    users = qs.filter(role="user")

    ctx = {
        "admins": admins,
        "users": users,
    }
    return render(request, "accounts/list.html", ctx)


@login_required
@user_passes_test(_is_admin)
def accounts_add(request):
    """
    Crea nuovo account. Password obbligatoria in create.
    Gestione lingue opzionale se esiste User.languages M2M.
    """
    if request.method == "POST":
        form = AccountForm(request.POST)
        if not request.POST.get("password"):
            form.add_error("password", "La password è obbligatoria per creare un account.")
        if form.is_valid():
            user = form.save(commit=True)
            # Lingue (opzionale)
            if HAS_LANGUAGE and hasattr(user, "m2m_languages"):
                lang_ids = request.POST.getlist("lang_ids")
                langs = Language.objects.filter(id__in=lang_ids)
                user.m2m_languages.set(langs)
            messages.success(request, "Account creato correttamente.")
            return redirect("accounts_list")
    else:
        form = AccountForm()

    languages = Language.objects.all().order_by("id") if HAS_LANGUAGE else []
    selected_lang_ids = []

    ctx = {
        "page_title": "Add account",
        "show_password": True,
        "form": form,
        "languages": languages,
        "selected_lang_ids": selected_lang_ids,
    }
    return render(request, "accounts/add.html", ctx)


@login_required
@user_passes_test(_is_admin)
def accounts_edit(request, user_id):
    """
    Modifica account esistente. Password opzionale: se vuota non cambia.
    Lingue gestite se M2M presente.
    """
    user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        form = AccountForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=True)
            if HAS_LANGUAGE and hasattr(user, "m2m_languages"):
                lang_ids = request.POST.getlist("lang_ids")
                langs = Language.objects.filter(id__in=lang_ids)
                user.m2m_languages.set(langs)
            messages.success(request, "Account aggiornato.")
            return redirect("accounts_list")
    else:
        form = AccountForm(instance=user)

    if HAS_LANGUAGE and hasattr(user, "m2m_languages"):
        selected_lang_ids = list(user.m2m_languages.values_list("id", flat=True))
        languages = Language.objects.all().order_by("id")
    else:
        selected_lang_ids = []
        languages = []

    ctx = {
        "page_title": "Edit account",
        "show_password": False,
        "form": form,
        "languages": languages,
        "selected_lang_ids": selected_lang_ids,
    }
    return render(request, "accounts/edit.html", ctx)
