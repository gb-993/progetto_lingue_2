from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from core import views_health  
from django.contrib.auth import views as auth_views
from core.views import test_500


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("", include("core.urls")),  
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("languages/", include("languages_ui.urls")),
    path("parameters/", include("parameters_ui.urls")),
    path("glossary/", include("glossary_ui.urls")),
    path("graphs/", include("graphs_ui.urls")),
    path("table-a/", include("tablea_ui.urls")),
    path("submissions/", include("submissions_ui.urls")),
    path("queries/", include("queries.urls")),
    path("health/", views_health.health, name="health"),
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("test500/", test_500, name="test_500"),
    path("instruction/", include("instruction_ui.urls")),
    path("questions/", include("questions_ui.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
