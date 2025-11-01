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
    # consente solo a admin/staff di gestire gli account
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

    if request.method == "POST":
        form = AccountForm(request.POST)
        if not request.POST.get("password"):
            form.add_error("password", "La password è obbligatoria per creare un account.")
        if form.is_valid():
            user = form.save(commit=True)
            if HAS_LANGUAGE and hasattr(user, "m2m_languages"):
                lang_ids = request.POST.getlist("lang_ids")
                langs = Language.objects.filter(id__in=lang_ids)

                conflicts = []
                for l in langs:
                    if l.assigned_user_id and l.assigned_user_id != user.id:
                        conflicts.append((l, l.assigned_user_id))

                if conflicts:
                    msg_lines = ["Alcune lingue risultano già assegnate ad altri utenti:"]
                    for l, other_uid in conflicts:
                        try:
                            other_user = User.objects.get(pk=other_uid)
                            other_label = other_user.email  
                        except User.DoesNotExist:
                            other_label = f"utente {other_uid}"

                        msg_lines.append(
                            f"- {l.id} → già assegnata. Vai all'utente {other_label} per rimuoverla prima di riassegnare."
                        )

                    form.add_error(None, "\n".join(msg_lines))

                    languages = Language.objects.all().order_by("id")
                    selected_lang_ids = [l.id for l in langs]
                    ctx = {
                        "page_title": "Add account",
                        "show_password": True,
                        "form": form,
                        "languages": languages,
                        "selected_lang_ids": selected_lang_ids,
                    }
                    return render(request, "accounts/add.html", ctx)

                # 2) Nessun conflitto -> salva M2M
                user.m2m_languages.set(langs)

                # 3) Sincronizza FK assegnazioni
                Language.objects.filter(id__in=lang_ids).update(assigned_user=user)
                Language.objects.filter(assigned_user=user).exclude(id__in=lang_ids).update(assigned_user=None)

            messages.success(request, "Account creato correttamente.")
            return redirect("accounts_list")

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

    if request.method == "POST":
        form = AccountForm(request.POST, instance=user)

        if form.is_valid():
            user = form.save(commit=True)

            if HAS_LANGUAGE and hasattr(user, "m2m_languages"):
                lang_ids = request.POST.getlist("lang_ids")
                langs = Language.objects.filter(id__in=lang_ids)

                # 1) Conflitti: lingua già assegnata via FK ad altro utente
                conflicts = []
                for l in langs:
                    if l.assigned_user_id and l.assigned_user_id != user.id:
                        conflicts.append((l, l.assigned_user_id))

                if conflicts:
                    # non conferma in automatico: mostra errore bloccante
                    msg_lines = ["Alcune lingue risultano già assegnate ad altri utenti:"]
                    for l, other_uid in conflicts:
                        try:
                            other_user = User.objects.get(pk=other_uid)
                            other_label = other_user.email  
                        except User.DoesNotExist:
                            other_label = f"utente {other_uid}"

                        msg_lines.append(
                            f"- {l.id} → già assegnata. Vai all'utente {other_label} per rimuoverla prima di riassegnare."
                        )

                    form.add_error(None, "\n".join(msg_lines))


                    languages = Language.objects.all().order_by("id")
                    selected_lang_ids = [l.id for l in langs]

                    ctx = {
                        "page_title": "Edit account",
                        "show_password": False,
                        "form": form,
                        "languages": languages,
                        "selected_lang_ids": selected_lang_ids,
                    }
                    return render(request, "accounts/edit.html", ctx)

                # 2) Nessun conflitto -> salva M2M
                user.m2m_languages.set(langs)
                # 3) sincronizza la FK di Language 
                Language.objects.filter(id__in=lang_ids).update(assigned_user=user)
                Language.objects.filter(assigned_user=user).exclude(id__in=lang_ids).update(assigned_user=None)

            messages.success(request, "Account updated")
            return redirect("accounts_list")

        # form non valido -> ricostruisci contesto e torna al template
        languages = Language.objects.all().order_by("id") if HAS_LANGUAGE else []
        selected_lang_ids = list(Language.objects.filter(assigned_user=user).values_list("id", flat=True)) \
            if HAS_LANGUAGE else []
        ctx = {
            "page_title": "Edit account",
            "show_password": False,
            "form": form,
            "languages": languages,
            "selected_lang_ids": selected_lang_ids,
        }
        return render(request, "accounts/edit.html", ctx)

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
            pwd_form = MyPasswordChangeForm(user=user)  
            if form.is_valid():
                form.save()
                messages.success(request, _("Profile data updated"))
                return redirect("my_account")
            else:
                messages.error(request, _("Correggi gli errori nel profilo."))
        elif action == "password":
            form = MyAccountForm(instance=user)  
            pwd_form = MyPasswordChangeForm(user=user, data=request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)  
                messages.success(request, _("Password successfully updated"))
                return redirect("my_account")
            else:
                messages.error(request, _("Correct the errors in the password"))
        else:
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


from core.models import ParameterChangeLog

@login_required
def dashboard(request):
    is_admin = (
        request.user.is_staff
        or request.user.is_superuser
        or getattr(request.user, "role", "") == "admin"
    )
    recent = []
    if is_admin:
        recent = (ParameterChangeLog.objects
                  .select_related("parameter", "changed_by")
                  .only("parameter__id", "changed_at", "changed_by__email", "recap", "diff")
                  .order_by("-changed_at")[:10])
    return render(request, "accounts/dashboard.html", {"is_admin": is_admin, "recent_param_changes": recent})
