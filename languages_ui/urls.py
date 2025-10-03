from django.urls import path
from . import views

urlpatterns = [
    path("", views.language_list, name="language_list"),
    path("add/", views.language_add, name="language_add"),
    path("<str:lang_id>/edit/", views.language_edit, name="language_edit"),
    path("<str:lang_id>/data/", views.language_data, name="language_data"),
    path("<str:lang_id>/answer/<str:question_id>/save/", views.answer_save, name="answer_save"),
    
    path("languages/<str:lang_id>/debug/", views.language_debug, name="language_debug"),

    # placeholder opzionali:
    path("<str:lang_id>/export/", views.language_export, name="language_export"),
    path("<str:lang_id>/debug/", views.language_debug, name="language_debug"),
    path("<str:lang_id>/save-instructions/", views.language_save_instructions, name="language_save_instructions"),
    path("<str:lang_id>/approve/", views.language_approve, name="language_approve"),
    path("<str:lang_id>/reopen/", views.language_reopen, name="language_reopen"),
]
