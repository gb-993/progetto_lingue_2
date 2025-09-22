from django.contrib import admin
from .models import (
    User, Glossary, Language, ParameterDef, Question,
    LanguageParameter, Answer, Example, Motivation, AnswerMotivation,
    LanguageParameterEval, Submission, SubmissionAnswer,
    SubmissionAnswerMotivation, SubmissionExample, SubmissionParam
)

# Registra TUTTO tranne ParameterDef (che gestiamo con ModelAdmin custom)
admin.site.register(User)
admin.site.register(Glossary)
admin.site.register(Language)
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

from parameters_ui.forms import ParameterForm  # <— cambia QUI il modulo di import

@admin.register(ParameterDef)
class ParameterDefAdmin(admin.ModelAdmin):
    form = ParameterForm
    list_display = ("id", "name", "position", "is_active")
    ordering = ("position",)
    search_fields = ("id", "name", "short_description", "implicational_condition")
