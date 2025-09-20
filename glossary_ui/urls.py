from django.urls import path
from . import views
urlpatterns = [
    path("", views.glossary_list, name="glossary_list"),
    path("add/", views.glossary_add, name="glossary_add"),
    path("<str:word>/save/", views.glossary_save, name="glossary_save"),
    path("<str:word>/delete/", views.glossary_delete, name="glossary_delete"),
]
