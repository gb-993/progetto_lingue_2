from django.urls import path
from . import views

urlpatterns = [
    path("all/", views.question_list, name="questions_list"),
]