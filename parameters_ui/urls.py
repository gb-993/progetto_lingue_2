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
]
