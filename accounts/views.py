from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")

@login_required
def accounts_list(request):
    return render(request, "accounts/list.html", {"admins": [], "users": []})

@login_required
def accounts_add(request):
    return render(request, "accounts/add.html", {"page_title": "Add account", "show_password": True, "languages": [], "selected_lang_ids": []})

@login_required
def accounts_edit(request, user_id):
    return render(request, "accounts/edit.html", {"page_title": "Edit account", "show_password": False, "languages": [], "selected_lang_ids": []})
