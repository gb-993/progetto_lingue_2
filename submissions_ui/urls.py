# submissions_ui/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.submissions_list, name="submissions_list"),
    path("<int:submission_id>/", views.submission_detail, name="submission_detail"),
    path("create/<str:language_id>/", views.submission_create_for_language, name="submission_create_for_language"),
path("create-all/", views.submission_create_all_languages, name="submission_create_all"),
path("delete-backup/", views.submission_delete_backup, name="submission_delete_backup"),
]
