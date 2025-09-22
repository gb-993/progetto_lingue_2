from django.urls import path
from . import views

urlpatterns = [
    path("", views.glossary_list, name="glossary_list"),
    path("add/", views.glossary_add, name="glossary_add"),
    path("<str:word>/", views.glossary_view, name="glossary_view"),
    path("<str:word>/edit/", views.glossary_edit, name="glossary_edit"),
    path("<str:word>/delete/", views.glossary_delete, name="glossary_delete"),
]
