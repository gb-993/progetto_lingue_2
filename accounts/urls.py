from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("login/",  auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.accounts_list, name="accounts_list"),
    path("add/", views.accounts_add, name="accounts_add"),
    path("<int:user_id>/edit/", views.accounts_edit, name="accounts_edit"),
]
