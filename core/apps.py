# core/apps.py — AGGIUNGI l'import in ready()

from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Import "eager" per registrare i signals
        from . import signals  # noqa: F401
