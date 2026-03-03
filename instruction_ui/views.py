from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from core.models import SiteContent
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST


def instruction_page(request):
    """
    Pagina Instruction, visibile a tutti (user e admin).
    Contenuto fittizio per ora.
    """
    return render(request, "instructions/instructions.html", {})

def _is_admin(user) -> bool:
    """Ruolo amministrativo o staff/superuser."""
    return (getattr(user, "role", "") == "admin") or bool(user.is_staff) or bool(user.is_superuser)



@login_required
def instruction(request):
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
def update_site_content(request):
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