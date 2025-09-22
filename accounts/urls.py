from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views
from .forms import EmailAuthForm


urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),   
    path("", views.accounts_list, name="accounts_list"),
    path("add/", views.accounts_add, name="accounts_add"),
    path("<int:user_id>/edit/", views.accounts_edit, name="accounts_edit"),
    path("login/", LoginView.as_view(
        template_name="accounts/login.html",
        authentication_form=EmailAuthForm,
        redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", LogoutView.as_view(next_page="/accounts/login/"), name="logout"),
]
