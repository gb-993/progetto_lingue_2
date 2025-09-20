from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def glossary_list(request):
    return render(request, "glossary/list.html", {"words": []})

@login_required
def glossary_add(request):
    return render(request, "glossary/add.html")

@login_required
def glossary_save(request, word):
    """
    Minimal save view for glossary terms.

    URL pattern provides a `word` string. For now we render an edit form on GET
    and accept POSTed 'term' and 'definition' fields and then redirect back to
    the list view. This is intentionally lightweight because no model exists in
    this app yet. Replace with model-backed logic when a `GlossaryEntry` model
    is added.
    """
    if request.method == "POST":
        term = request.POST.get("term", "").strip()
        definition = request.POST.get("definition", "").strip()
        # Here you'd normally save to the database. We'll fake a saved word and
        # redirect back to the list view.
        from django.shortcuts import redirect

        return redirect("glossary_list")

    # GET: render the edit form with the provided word as the id/term
    return render(
        request,
        "glossary/edit.html",
        {"word": {"id": word, "term": word, "definition": ""}},
    )


@login_required
def glossary_delete(request, word):
    """Minimal delete view placeholder.

    Currently there is no model backing glossary entries. This view simply
    accepts the request and redirects back to the list. Replace with real
    deletion logic when a model is added.
    """
    from django.shortcuts import redirect

    # A real implementation would check request.method and permissions and
    # delete the model instance. For now, just redirect back to the list.
    return redirect("glossary_list")
