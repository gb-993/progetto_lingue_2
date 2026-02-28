from django.urls import path
from . import views
urlpatterns = [
    path("", views.parameter_list, name="parameter_list"),
    path("add/", views.parameter_add, name="parameter_add"),
    path("<str:param_id>/edit/", views.parameter_edit, name="parameter_edit"),
    path("<str:param_id>/deactivate/", views.parameter_deactivate, name="parameter_deactivate"),
    path("parameters/<str:param_id>/questions/add/", views.question_add, name="question_add"),
    path("parameters/<str:param_id>/questions/<str:question_id>/edit/", views.question_edit, name="question_edit"),
    path("parameters/<str:param_id>/questions/<str:question_id>/delete/", views.question_delete, name="question_delete"),
    path("languages/<str:lang_id>/review-flags/", views.review_flags_list, name="review_flags_list"),
    path("languages/<str:lang_id>/parameters/<str:param_id>/review-flag/", views.toggle_review_flag, name="toggle_review_flag"),
    path("lookups/", views.lookups_manage, name="param_lookups_manage"),
    path("parameters/motivations/", views.motivations_manage, name="motivations_manage"),
    path("<str:param_id>/questions/import/", views.question_clone, name="question_clone"),
    path('parameters/<str:param_id>/pdf/', views.parameter_download_pdf, name='parameter_download_pdf'),



]
