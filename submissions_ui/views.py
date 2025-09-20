from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def submissions_list(request):
    return render(request, "submissions/list.html", {"submissions": []})
