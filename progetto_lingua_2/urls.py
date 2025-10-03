from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from core import views_health  

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("languages/", include("languages_ui.urls")),
    path("parameters/", include("parameters_ui.urls")),
    path("glossary/", include("glossary_ui.urls")),
    path("table-a/", include("tablea_ui.urls")),
    path("submissions/", include("submissions_ui.urls")),

    path("health/", views_health.health, name="health"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
