from django.urls import path
from . import views

urlpatterns = [
    path("languages/", views.language_list, name="language_list"),
    path("languages/add/", views.language_add, name="language_add"),
    path("languages/<str:lang_id>/edit/", views.language_edit, name="language_edit"),

    path("languages/<str:lang_id>/", views.language_data, name="language_data"),
    path("languages/<str:lang_id>/export/", views.language_export_xlsx, name="language_export_xlsx"),
    path("languages/<str:lang_id>/debug/", views.language_debug, name="language_debug"),
    path("languages/<str:lang_id>/run_dag/", views.language_run_dag, name="language_run_dag"),

    path("languages/<str:lang_id>/answers/<str:question_id>/save/", views.answer_save, name="answer_save"),
    path("languages/<str:lang_id>/answers/bulk_save/", views.answers_bulk_save, name="answers_bulk_save"),

    # nuove azioni di stato
    path("languages/<str:lang_id>/submit/", views.language_submit, name="language_submit"),
    path("languages/<str:lang_id>/approve/", views.language_approve, name="language_approve"),
    path("languages/<str:lang_id>/reject/", views.language_reject, name="language_reject"),
    path("languages/<str:lang_id>/reopen/", views.language_reopen, name="language_reopen"),
]
