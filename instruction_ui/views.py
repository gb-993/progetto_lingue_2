from typing import Any

import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import SiteContent
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST


def instruction_page(request: HttpRequest) -> HttpResponse:
    """Render the public instructions page.

    Args:
        request: Incoming HTTP request.

    Returns:
        Rendered instructions page response.
    """
    return render(request, "instructions/instructions.html", {})


def _is_admin(user: Any) -> bool:
    """Check whether a user has administrative privileges.

    Args:
        user: User-like object attached to the request.

    Returns:
        ``True`` if the user has role ``admin`` or is staff/superuser,
        otherwise ``False``.
    """
    return (getattr(user, "role", "") == "admin") or bool(user.is_staff) or bool(user.is_superuser)



@login_required
def instruction(request: HttpRequest) -> HttpResponse:
    """Render the instructions page with dynamic content from the database.

    The view loads all `SiteContent` entries whose key starts with
    ``instr_`` and exposes them as a key/content mapping for template usage.

    Args:
        request: Current authenticated HTTP request.

    Returns:
        Rendered instructions page response enriched with dynamic content and
        admin flag.
    """
    # 1. Recuperiamo tutti i contenuti salvati nel DB che riguardano le istruzioni
    dynamic_contents = SiteContent.objects.filter(key__startswith="instr_")
    
    # 2. Trasformiamo la query in un dizionario: {'chiave': 'testo dal db'}
    content_dict = {item.key: item.content for item in dynamic_contents}

    # 3. Controlliamo se l'utente è un admin
    is_admin = _is_admin(request.user)

    # 4. Passiamo i dati al template
    ctx = {
        "is_admin": is_admin,
        "content": content_dict,
        "page_title": "Instructions",
    }
    
    # LA RIGA CORRETTA È QUESTA:
    return render(request, "instructions/instructions.html", ctx)



@login_required
@require_POST
def update_site_content(request: HttpRequest) -> JsonResponse:
    """Create or update a `SiteContent` entry for the instructions page.

    Access is restricted to admin users and POST requests. The payload is
    expected as JSON with at least ``key`` and optional ``content``/``page``.

    Args:
        request: Current authenticated HTTP request.

    Returns:
        JSON response with status ``success`` on write completion, or an error
        payload with HTTP 4xx/5xx status code.
    """
    # Controllo di sicurezza ferreo
    if not _is_admin(request.user):
        return JsonResponse({"error": "Unauthorized"}, status=403)
    
    try:
        data = json.loads(request.body)
        key = data.get("key")
        content = data.get("content", "")
        page_name = data.get("page", "Instructions") # Usiamo un default

        if not key:
            return JsonResponse({"error": "Key is required"}, status=400)

        # Cerca il record con questa chiave e lo aggiorna, se non esiste lo crea
        SiteContent.objects.update_or_create(
            key=key,
            defaults={
                "content": content.strip(),
                "page": page_name,
                "updated_by": request.user
            }
        )
        return JsonResponse({"status": "success"})
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)