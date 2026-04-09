from typing import Any

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import update_session_auth_hash
from django.utils.translation import gettext as _
from core.models import ParameterChangeLog, Submission, ParameterReviewFlag
from .forms import AccountForm, MyAccountForm, MyPasswordChangeForm
from core.models import ParameterDef, Answer, Glossary, User, Question, SiteContent
try:
    from core.models import Language
    HAS_LANGUAGE = True
except Exception:
    Language = None
    HAS_LANGUAGE = False


def _is_admin(user: User) -> bool:
    """Return whether the given user should be treated as an administrator.

    Args:
        user: User instance to evaluate.

    Returns:
        ``True`` when the user is authenticated and has staff privileges or
        role ``admin``; otherwise ``False``.
    """
    return bool(user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin"))


# ASSICURATI CHE NON CI SIA @login_required QUI
def dashboard(request: HttpRequest) -> HttpResponse:
    """Render the main dashboard with role-specific widgets and statistics."""
    user = request.user
    
    # 1. INTERCETTA L'UTENTE NON AUTENTICATO (ANONIMO)
    if not user.is_authenticated:
        role = "public"
        is_admin = False
    else:
        role = getattr(user, "role", "user")
        is_admin = _is_admin(user)

    # 2. STATISTICHE GLOBALI (calcolate per tutti)
    total_questions = Question.objects.filter(parameter__is_active=True).count()

    completed_langs_count = Language.objects.annotate(
        valid_answers_count=Count('answers', filter=Q(
            answers__response_text__in=['yes', 'no'],
            answers__question__parameter__is_active=True
        ))
    ).filter(valid_answers_count__gte=total_questions).count()

    stats = {
        "languages": Language.objects.count(),
        "completed_languages": completed_langs_count,
        "families": Language.objects.exclude(family="").values("family").distinct().count(),
        "parameters": ParameterDef.objects.filter(is_active=True).count(),
        "answers": Answer.objects.count(),
        "glossary": Glossary.objects.count(),
    }

    # 3. RITORNO ANTICIPATO PER UTENTI PUBBLICI O ANONIMI
    # Se è public/anonimo, renderizza subito e BLOCCA l'esecuzione del resto della funzione
    if role == "public":
        return render(request, "accounts/public_dashboard.html", {"stats": stats, "is_public": True})

    # ==========================================
    # DA QUI IN POI CI ARRIVANO SOLO I LOGGATI
    # ==========================================
    ctx: dict[str, Any] = {"is_admin": is_admin, "stats": stats}

    # --- LOGICA ADMIN ---
    if is_admin:
        ctx["pending_languages"] = Language.objects.filter(
            answers__status="waiting_for_approval"
        ).distinct()

        ctx["recent_param_changes"] = (
            ParameterChangeLog.objects
            .select_related("parameter", "changed_by")
            .order_by("-changed_at")[:10]
        )

        red_langs = (
            ParameterReviewFlag.objects.filter(flag=True)
            .values('language__id', 'language__name_full')
            .annotate(red_count=Count('parameter', distinct=True))
            .filter(red_count__gt=0)
            .order_by('-red_count')
        )
        
        stats["total_red"] = sum(item['red_count'] for item in red_langs)
        ctx["red_langs"] = red_langs

    # --- LOGICA USER ---
    elif role == "user":  # Usa elif per maggiore sicurezza
        total_q_count = Question.objects.filter(parameter__is_active=True).count()
        # Qui user.m2m_languages è sicuro perché sappiamo che l'utente è loggato!
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
def accounts_list(request: HttpRequest) -> HttpResponse:
    """List all accounts grouped by role, with optional text search.

    Args:
        request: Current authenticated admin request.

    Returns:
        Rendered account list page containing admin, user, and public groups.
    """
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
def accounts_add(request: HttpRequest) -> HttpResponse:
    """Create a new account and optionally assign languages.

    On POST, validates form data, checks assignment conflicts for selected
    languages, and persists the user plus language bindings atomically.

    Args:
        request: Current authenticated admin request.

    Returns:
        Account creation page on GET/validation error, or redirect to
        ``accounts_list`` on success.
    """
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
def accounts_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    """Update an existing account and its language assignments.

    On POST, validates the account form, checks that requested languages are
    not already bound to another user, then saves all updates in one
    transaction.

    Args:
        request: Current authenticated admin request.
        user_id: Primary key of the account being edited.

    Returns:
        Account edit page on GET/validation error, or redirect to
        ``accounts_list`` on success.
    """
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
def my_account(request: HttpRequest) -> HttpResponse:
    """Handle profile and password updates for the current user.

    The action is selected via the ``action`` POST field and processed with
    the appropriate form pair.

    Args:
        request: Current authenticated request.

    Returns:
        Rendered self-service account page, or redirect back to the same page
        after successful profile/password update.
    """
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
def accounts_delete(request: HttpRequest, user_id: int) -> HttpResponse:
    """Delete an account after guard checks and show a deletion recap.

    The view blocks self-deletion and deletion of the last administrator.
    Before deleting, it computes related object counters; on POST it performs
    cleanup (language unassignment, M2M cleanup, submission anonymization)
    inside a transaction and then deletes the user.

    Args:
        request: Current authenticated admin request.
        user_id: Primary key of the account to delete.

    Returns:
        Confirmation page on GET, or redirect to ``accounts_list`` on POST.
    """

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
def accept_terms(request: HttpRequest) -> HttpResponse:
    """Persist acceptance of terms of use for the current user.

    If terms are already accepted, the user is redirected immediately to the
    dashboard. On valid POST, the acceptance timestamp is stored.

    Args:
        request: Current authenticated request.

    Returns:
        Terms acceptance page or redirect to the requested ``next`` target (or
        dashboard fallback) after successful acceptance.
    """
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
            messages.error(request, "Please check the box to continue.")

    return render(request, "accounts/accept_terms.html")



def how_to_cite(request: HttpRequest) -> HttpResponse:
    """Render the public "how to cite" page with editable site content.

    Args:
        request: Incoming HTTP request (authenticated or anonymous).

    Returns:
        Rendered citation page containing key/value content blocks and admin
        visibility flag.
    """
    is_admin = _is_admin(request.user)
    
    contents = SiteContent.objects.all()
    site_contents = {item.key: item.content for item in contents}
    
    ctx = {
        'site_contents': site_contents,
        'is_admin': is_admin
    }
    return render(request, 'accounts/how_to_cite.html', ctx)


@login_required
@user_passes_test(_is_admin)
def edit_site_content(request: HttpRequest, key: str) -> HttpResponse:
    """Create or update a ``SiteContent`` entry for the citation page.

    Args:
        request: Current authenticated admin request.
        key: Content key to edit.

    Returns:
        Content edit page on GET, or redirect to ``how_to_cite`` on success.
    """
    content_obj, _created = SiteContent.objects.get_or_create(
        key=key,
        defaults={'page': 'how_to_cite', 'content': ''}
    )
    
    if request.method == "POST":
        # Salvataggio
        content_obj.content = request.POST.get('content', '')
        content_obj.page = 'how_to_cite'  
        content_obj.updated_by = request.user
        content_obj.save()
        
        messages.success(request, f"Contenuto '{key}' aggiornato con successo!")
        return redirect('how_to_cite')
        
    ctx = {
        'obj': content_obj,
        'page_title': f"Modifica {key}"
    }
    return render(request, 'accounts/edit_site_content.html', ctx)