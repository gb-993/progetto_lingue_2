from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import update_session_auth_hash
from django.utils.translation import gettext as _
from core.models import User, ParameterChangeLog
from .forms import AccountForm, MyAccountForm, MyPasswordChangeForm
try:
    from core.models import Language
    HAS_LANGUAGE = True
except Exception:
    Language = None
    HAS_LANGUAGE = False


def _is_admin(user: User) -> bool:
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


@login_required
def dashboard(request):
    is_admin = (
        request.user.is_staff
        or request.user.is_superuser
        or getattr(request.user, "role", "") == "admin"
    )

    recent = []
    if is_admin:
        recent = (
            ParameterChangeLog.objects
            .select_related("parameter", "changed_by")
            .only("parameter__id", "changed_at", "changed_by__email", "recap", "diff")
            .order_by("-changed_at")[:10]
        )

    return render(request, "accounts/dashboard.html", {
        "is_admin": is_admin,
        "recent_param_changes": recent,
    })


@login_required
@user_passes_test(_is_admin)
def accounts_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = User.objects.order_by("surname", "name", "email")
    if q:
        qs = qs.filter(
            Q(email__icontains=q) |
            Q(name__icontains=q) |
            Q(surname__icontains=q)
        )

    ctx = {
        "admins": qs.filter(role="admin"),
        "users": qs.filter(role="user"),
    }
    return render(request, "accounts/list.html", ctx)


@login_required
@user_passes_test(_is_admin)
def accounts_add(request):
    if request.method == "POST":
        form = AccountForm(request.POST)
        if not request.POST.get("password"):
            form.add_error("password", _("Password is required to create an account."))

        if form.is_valid():
            user = form.save(commit=False)
            lang_ids = request.POST.getlist("lang_ids") if HAS_LANGUAGE else []
            langs = Language.objects.filter(id__in=lang_ids) if HAS_LANGUAGE else []

            # Conflict detection
            conflicts = []
            if HAS_LANGUAGE:
                for l in langs:
                    if l.assigned_user_id and l.assigned_user_id != user.id:
                        conflicts.append((l, l.assigned_user_id))

            if conflicts:
                msg_lines = [_("Some languages are already assigned to other users:")]
                for l, other_uid in conflicts:
                    try:
                        other_user = User.objects.get(pk=other_uid)
                        other_label = other_user.email
                    except User.DoesNotExist:
                        other_label = f"user {other_uid}"
                    msg_lines.append(
                        f"- {l.id} → already assigned to {other_label}. "
                        "Please unassign it before reassigning."
                    )
                form.add_error(None, "\n".join(msg_lines))
            else:
                with transaction.atomic():
                    user.save()
                    if HAS_LANGUAGE:
                        user.m2m_languages.set(langs)
                        Language.objects.filter(id__in=lang_ids).update(assigned_user=user)
                        Language.objects.filter(assigned_user=user).exclude(id__in=lang_ids).update(assigned_user=None)

                messages.success(request, _("Account successfully created."))
                return redirect("accounts_list")

    else:
        form = AccountForm()

    ctx = {
        "page_title": _("Add account"),
        "show_password": True,
        "form": form,
        "languages": Language.objects.all().order_by("id") if HAS_LANGUAGE else [],
        "selected_lang_ids": [],
    }
    return render(request, "accounts/add.html", ctx)


@login_required
@user_passes_test(_is_admin)
def accounts_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        form = AccountForm(request.POST, instance=user)
        if form.is_valid():
            updated_user = form.save(commit=False)
            lang_ids = request.POST.getlist("lang_ids") if HAS_LANGUAGE else []
            langs = Language.objects.filter(id__in=lang_ids) if HAS_LANGUAGE else []

            conflicts = []
            if HAS_LANGUAGE:
                for l in langs:
                    if l.assigned_user_id and l.assigned_user_id != user.id:
                        conflicts.append((l, l.assigned_user_id))

            if conflicts:
                msg_lines = [_("Some languages are already assigned to other users:")]
                for l, other_uid in conflicts:
                    try:
                        other_user = User.objects.get(pk=other_uid)
                        other_label = other_user.email
                    except User.DoesNotExist:
                        other_label = f"user {other_uid}"
                    msg_lines.append(
                        f"- {l.id} → already assigned to {other_label}. "
                        "Please unassign it before reassigning."
                    )
                form.add_error(None, "\n".join(msg_lines))
            else:
                with transaction.atomic():
                    updated_user.save()
                    if HAS_LANGUAGE:
                        updated_user.m2m_languages.set(langs)
                        Language.objects.filter(id__in=lang_ids).update(assigned_user=updated_user)
                        Language.objects.filter(assigned_user=updated_user).exclude(id__in=lang_ids).update(assigned_user=None)

                messages.success(request, _("Account successfully updated."))
                return redirect("accounts_list")

    else:
        form = AccountForm(instance=user)

    ctx = {
        "page_title": _("Edit account"),
        "show_password": False,
        "form": form,
        "languages": Language.objects.all().order_by("id") if HAS_LANGUAGE else [],
        "selected_lang_ids": list(Language.objects.filter(assigned_user=user).values_list("id", flat=True)) if HAS_LANGUAGE else [],
    }
    return render(request, "accounts/edit.html", ctx)


@login_required
def my_account(request):
    user = request.user

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "profile":
            form = MyAccountForm(request.POST, instance=user)
            pwd_form = MyPasswordChangeForm(user=user)
            if form.is_valid():
                form.save()
                messages.success(request, _("Profile information updated."))
                return redirect("my_account")
            else:
                messages.error(request, _("Please correct the profile errors."))

        elif action == "password":
            form = MyAccountForm(instance=user)
            pwd_form = MyPasswordChangeForm(user=user, data=request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, _("Password successfully updated."))
                return redirect("my_account")
            else:
                messages.error(request, _("Please correct the password errors."))

        else:
            form = MyAccountForm(instance=user)
            pwd_form = MyPasswordChangeForm(user=user)
    else:
        form = MyAccountForm(instance=request.user)
        pwd_form = MyPasswordChangeForm(user=request.user)

    ctx = {
        "page_title": _("My Account"),
        "form": form,
        "pwd_form": pwd_form,
    }
    return render(request, "accounts/my_account.html", ctx)
