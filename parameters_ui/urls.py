from django.urls import path
from . import views
urlpatterns = [
    path("", views.parameter_list, name="parameter_list"),
    path("add/", views.parameter_add, name="parameter_add"),
    path("<str:param_id>/edit/", views.parameter_edit, name="parameter_edit"),
    path("<str:param_id>/deactivate/", views.parameter_deactivate, name="parameter_deactivate"),

]
