from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import update_session_auth_hash
from django.utils.translation import gettext as _
from core.models import User, ParameterChangeLog, Submission, ParameterReviewFlag
from .forms import AccountForm, MyAccountForm, MyPasswordChangeForm
from core.models import Language, ParameterDef, Answer, Glossary, User, Question
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
    user = request.user
    role = getattr(user, "role", "user")
    is_admin = _is_admin(user)

    total_langs = Language.objects.count()
    total_questions = Question.objects.filter(parameter__is_active=True).count()
    total_possible_answers = total_langs * total_questions

    completed_langs_count = Language.objects.annotate(
        valid_answers_count=Count('answers', filter=Q(
            answers__response_text__in=['yes', 'no'],
            answers__question__parameter__is_active=True
        ))
    ).filter(valid_answers_count__gte=total_questions).count()


    # Statistiche generali
    stats = {
        "languages": Language.objects.count(),
        "answers": Answer.objects.filter(response_text__in=["yes", "no"]).count(),
        "total_answers": total_possible_answers,
        "completed_languages": completed_langs_count,
    }

    if role == "public":
        return render(request, "accounts/public_dashboard.html", {"stats": stats, "is_public": True})

    ctx = {"is_admin": is_admin, "stats": stats}

    # --- LOGICA ADMIN: 50/50 Layout ---
    if is_admin:
        # Recuperiamo le lingue che hanno risposte in attesa
        ctx["pending_languages"] = Language.objects.filter(
            answers__status="waiting_for_approval"
        ).distinct()

        ctx["recent_param_changes"] = (
            ParameterChangeLog.objects
            .select_related("parameter", "changed_by")
            .order_by("-changed_at")[:10]
        )

    # --- LOGICA USER: Solo i suoi progetti ---
    if role == "user":
        total_q_count = Question.objects.filter(parameter__is_active=True).count()
        # Ottimizzazione: una sola query per tutto il progresso
        assigned_langs = user.m2m_languages.annotate(
            done_count=Count('answers', filter=Q(answers__response_text__in=['yes', 'no'])),
            has_reject=Count('answers', filter=Q(answers__status='rejected'))
        )

        user_projects = []
        for lang in assigned_langs:
            progress = int((lang.done_count / total_q_count) * 100) if total_q_count > 0 else 0
            user_projects.append({
                "lang": lang,
                "progress": progress,
                "has_rejection": lang.has_reject > 0,
            })
        ctx["user_projects"] = user_projects

    return render(request, "accounts/dashboard.html", ctx)


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
        "public_users": qs.filter(role="public"),
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


@login_required
@user_passes_test(_is_admin)
def accounts_delete(request, user_id: int):
  
    user = get_object_or_404(User, pk=user_id)

    #  no self-delete
    if request.user.pk == user.pk:
        messages.error(request, _("You cannot delete your own account."))
        return redirect("accounts_list")

    # Guardrail: no delete ultimo admin
    target_is_admin = bool(
        user.is_staff
        or user.is_superuser
        or getattr(user, "role", "") == "admin"
    )

    if target_is_admin:
        remaining_admins = (
            User.objects
            .filter(Q(is_staff=True) | Q(is_superuser=True) | Q(role="admin"))
            .exclude(pk=user.pk)
            .count()
        )
        if remaining_admins == 0:
            messages.error(request, _("You cannot delete the last administrator."))
            return redirect("accounts_list")


    # --- recap counts (usati sia in GET sia per messaggi finali) ---
    assigned_lang_qs = Language.objects.filter(assigned_user=user).order_by("id") if HAS_LANGUAGE else Language.objects.none()
    assigned_lang_count = assigned_lang_qs.count() if HAS_LANGUAGE else 0

    m2m_lang_count = user.m2m_languages.count()
    submission_count = Submission.objects.filter(submitted_by=user).count()
    reviewflag_count = ParameterReviewFlag.objects.filter(user=user).count()
    changelog_count = ParameterChangeLog.objects.filter(changed_by=user).count()

    if request.method == "POST":
        with transaction.atomic():
            # 1) Unassign languages (assigned_user -> NULL)
            if HAS_LANGUAGE and assigned_lang_count:
                assigned_lang_qs.update(assigned_user=None)

            # 2) Clear M2M languages
            user.m2m_languages.clear()

            # 3) Submission author -> NULL (esplicito, oltre a on_delete=SET_NULL)
            if submission_count:
                Submission.objects.filter(submitted_by=user).update(submitted_by=None)

            # 4) Delete user (ReviewFlags CASCADE, ChangeLog SET_NULL, etc.)
            user.delete()

        messages.success(
            request,
            _("Account deleted. Unassigned languages: %(a)s. Removed M2M links: %(m)s. "
              "Submissions anonymized: %(s)s. Review flags removed: %(r)s. "
              "Change logs anonymized: %(c)s.") % {
                "a": assigned_lang_count,
                "m": m2m_lang_count,
                "s": submission_count,
                "r": reviewflag_count,
                "c": changelog_count,
            }
        )
        return redirect("accounts_list")

    # GET: pagina recap
    ctx = {
        "page_title": _("Delete account"),
        "u": user,
        "assigned_lang_count": assigned_lang_count,
        "assigned_lang_list": list(assigned_lang_qs[:12]) if HAS_LANGUAGE else [],
        "m2m_lang_count": m2m_lang_count,
        "m2m_lang_list": list(user.m2m_languages.all().order_by("id")[:12]),
        "submission_count": submission_count,
        "reviewflag_count": reviewflag_count,
        "changelog_count": changelog_count,
    }
    return render(request, "accounts/delete_confirm.html", ctx)


@login_required
def accept_terms(request):
    # Se l'utente ha già accettato, lo mandiamo via
    if request.user.terms_accepted:
        return redirect('dashboard')

    if request.method == "POST":
        if request.POST.get("accept") == "on":
            request.user.terms_accepted = True
            request.user.terms_accepted_at = timezone.now()
            request.user.save(update_fields=["terms_accepted", "terms_accepted_at"])
            return redirect(request.GET.get('next', 'dashboard'))
        else:
            messages.error(request, "Devi spuntare la casella per poter continuare.")

    return render(request, "accounts/accept_terms.html")