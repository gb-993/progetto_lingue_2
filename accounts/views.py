from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from core.models import User
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _

from .forms import MyAccountForm, MyPasswordChangeForm
try:
    from core.models import Language
    HAS_LANGUAGE = True
except Exception:
    Language = None
    HAS_LANGUAGE = False

from .forms import AccountForm, MyAccountForm


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

    # se admin ha inviato il form
    if request.method == "POST":
        form = AccountForm(request.POST)
        # controllo subito password obbligatoria
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
    # richiesta GET, admin apre la pagina per la prima volta    
    else:
        form = AccountForm()

    # serve per il multi-select delle lingue
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

    user = get_object_or_404(User, pk=user_id)

    # se admin ha inviato il form
    if request.method == "POST":
        # form collegato all'istanza esistente di User così da fare update
        form = AccountForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=True) # scrive subito sul db
            if HAS_LANGUAGE and hasattr(user, "m2m_languages"):
                lang_ids = request.POST.getlist("lang_ids")
                langs = Language.objects.filter(id__in=lang_ids)
                user.m2m_languages.set(langs)
            messages.success(request, "Account aggiornato.")
            return redirect("accounts_list")
        
    # se richiesta GET, mostra il form con i dati esistenti
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



@login_required
def my_account(request):
    """
    Pagina unica: profilo + cambio password per l'utente corrente.
    Due form indipendenti nello stesso template:
      - POST action=profile  -> salva MyAccountForm
      - POST action=password -> salva MyPasswordChangeForm
    Mantiene la sessione valida dopo il cambio password.
    """
    user = request.user

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile":
            form = MyAccountForm(request.POST, instance=user)
            pwd_form = MyPasswordChangeForm(user=user)  # form vuota per la sezione password
            if form.is_valid():
                form.save()
                messages.success(request, _("Dati profilo aggiornati."))
                return redirect("my_account")
            else:
                messages.error(request, _("Correggi gli errori nel profilo."))
        elif action == "password":
            form = MyAccountForm(instance=user)  # profilo non toccato in questo POST
            pwd_form = MyPasswordChangeForm(user=user, data=request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)  # evita logout
                messages.success(request, _("Password aggiornata correttamente."))
                return redirect("my_account")
            else:
                messages.error(request, _("Correggi gli errori nella password."))
        else:
            # fallback: tratta come GET
            form = MyAccountForm(instance=user)
            pwd_form = MyPasswordChangeForm(user=user)
    else:
        form = MyAccountForm(instance=request.user)
        pwd_form = MyPasswordChangeForm(user=request.user)

    ctx = {
        "page_title": "My Account",
        "form": form,
        "pwd_form": pwd_form,
    }
    return render(request, "accounts/my_account.html", ctx)
