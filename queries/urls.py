from django.urls import path
from . import views

app_name = "queries"
urlpatterns = [
    path("", views.home, name="home"),
]
