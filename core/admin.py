from django.contrib import admin
from languages_ui.forms import LanguageForm

from parameters_ui.forms import ParameterForm  # <— cambia QUI il modulo di import

from .models import (
    User, Glossary, Language, ParameterDef, Question,
    LanguageParameter, Answer, Example, Motivation, AnswerMotivation,
    LanguageParameterEval, Submission, SubmissionAnswer,
    SubmissionAnswerMotivation, SubmissionExample, SubmissionParam
)

# Registra TUTTO tranne ParameterDef (che gestiamo con ModelAdmin custom)
admin.site.register(User)
admin.site.register(Glossary)
admin.site.register(Question)
admin.site.register(LanguageParameter)
admin.site.register(Answer)
admin.site.register(Example)
admin.site.register(Motivation)
admin.site.register(AnswerMotivation)
admin.site.register(LanguageParameterEval)
admin.site.register(Submission)
admin.site.register(SubmissionAnswer)
admin.site.register(SubmissionAnswerMotivation)
admin.site.register(SubmissionExample)
admin.site.register(SubmissionParam)


@admin.register(ParameterDef)
class ParameterDefAdmin(admin.ModelAdmin):
    form = ParameterForm
    list_display = ("id", "name", "position", "is_active")
    ordering = ("position",)
    search_fields = ("id", "name", "short_description", "implicational_condition")


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    form = LanguageForm
    list_display = ("id", "name_full", "position", "assigned_user", "isocode", "glottocode", "grp")
    ordering = ("position",)
    search_fields = ("id","name_full","isocode","glottocode","grp","informant","supervisor","assigned_user__email",)
    list_filter = ("grp",)
    raw_id_fields = ("assigned_user",)
    list_per_page = 50
    # attivabile manualmente se serve dalla UI di admin (non nel sito)
    actions = ["recompact_positions"]

    def recompact_positions(self, request, queryset):
        """
        Ricompatta tutte le posizioni delle lingue (ignora il queryset).
        Risistema da 1 a N senza buchi né duplicati.
        """
        from django.db import transaction

        with transaction.atomic():
            for idx, lang in enumerate(Language.objects.order_by("position"), start=1):
                if lang.position != idx:
                    lang.position = idx
                    lang.save(update_fields=["position"])
        self.message_user(request, "Posizioni ricompattate con successo.")

    recompact_positions.short_description = "Ricompatta tutte le posizioni"
