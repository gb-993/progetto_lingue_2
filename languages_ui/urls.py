from django.urls import path
from . import views

urlpatterns = [
    # lista / CRUD lingue
    path("", views.language_list, name="language_list"),
    path("add/", views.language_add, name="language_add"),
    path("<str:lang_id>/edit/", views.language_edit, name="language_edit"),
    path("<str:lang_id>/delete/", views.language_delete, name="language_delete"),

    # NEW: import da Excel – DEVE stare prima della catch-all <str:lang_id>/
    path("import-excel/", views.language_import_excel, name="language_import_excel"),

    # dettaglio lingua + azioni
    path("<str:lang_id>/", views.language_data, name="language_data"),
    path("<str:lang_id>/export/", views.language_export_xlsx, name="language_export_xlsx"),
    path("<str:lang_id>/debug/", views.language_debug, name="language_debug"),
    path("<str:lang_id>/run_dag/", views.language_run_dag, name="language_run_dag"),

    path("<str:lang_id>/answers/<str:question_id>/save/", views.answer_save, name="answer_save"),
    path("<str:lang_id>/parameters/<str:param_id>/save/", views.parameter_save, name="parameter_save"),

    path("<str:lang_id>/submit/", views.language_submit, name="language_submit"),
    path("<str:lang_id>/approve/", views.language_approve, name="language_approve"),
    path("<str:lang_id>/reject/", views.language_reject, name="language_reject"),
    path("<str:lang_id>/reopen/", views.language_reopen, name="language_reopen"),

    path("<str:lang_id>/review-flags/", views.review_flags_list, name="review_flags_list"),
    path("<str:lang_id>/review-flags/<str:param_id>/toggle/", views.toggle_review_flag, name="toggle_review_flag"),

    path("export.xlsx", views.language_list_export_xlsx, name="language_list_export_xlsx"),
    path("export-all.zip", views.language_export_all_zip, name="language_export_all_zip"),

]
