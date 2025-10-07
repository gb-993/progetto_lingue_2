# submissions_ui/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.submissions_list, name="submissions_list"),
    path("<int:submission_id>/", views.submission_detail, name="submission_detail"),
    path("create/<str:language_id>/", views.submission_create_for_language, name="submission_create_for_language"),
]
