from django.urls import path
from . import views
urlpatterns = [
    path("", views.submissions_list, name="submissions_list"),
    
]
