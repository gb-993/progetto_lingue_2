from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from core.models import Language

@login_required
def language_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Language.objects.order_by("position")
    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(name_full__icontains=q) |
            Q(isocode__icontains=q) |
            Q(glottocode__icontains=q) |
            Q(grp__icontains=q) |
            Q(informant__icontains=q) |
            Q(supervisor__icontains=q)
        )
    return render(request, "languages/list.html", {"languages": qs, "q": q})

@login_required
def language_add(request):
    return render(request, "languages/add.html", {"page_title": "Add language", "form": {}})

@login_required
def language_edit(request, lang_id):
    return render(request, "languages/edit.html", {"page_title": "Edit language", "form": {}})

@login_required
@login_required
def language_data(request, lang_id):
    lang = get_object_or_404(Language, pk=lang_id)
    return render(request, "languages/data.html", {"language": lang})

@login_required
def language_export(request, lang_id):  # placeholder
    return render(request, "languages/data.html", {"language": {"id": lang_id, "name_full": "Example"}})

@login_required
def language_debug(request, lang_id):  # placeholder
    return render(request, "languages/data.html", {"language": {"id": lang_id, "name_full": "Example"}})

@login_required
def language_save_instructions(request, lang_id):  # placeholder
    return render(request, "languages/data.html", {"language": {"id": lang_id, "name_full": "Example"}})

@login_required
def language_approve(request, lang_id):  # placeholder
    return render(request, "languages/data.html", {"language": {"id": lang_id, "name_full": "Example"}})

@login_required
def language_reopen(request, lang_id):  # placeholder
    return render(request, "languages/data.html", {"language": {"id": lang_id, "name_full": "Example"}})

@login_required
def answer_save(request, lang_id, question_id):  # placeholder
    return render(request, "languages/data.html", {"language": {"id": lang_id, "name_full": "Example"}})
