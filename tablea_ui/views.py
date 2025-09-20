from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def tablea_index(request):
    ctx = {"languages": [], "parameters": [], "tableA": {"px": {}}}
    return render(request, "tablea/index.html", ctx)

@login_required
def tablea_export_xlsx(request):
    return tablea_index(request)  # placeholder

@login_required
def tablea_export_csv(request):
    return tablea_index(request)  # placeholder
