# core/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

from core.models import Answer
from core.services.param_consolidate import recompute_and_persist_language_parameter  # type: ignore[reportMissingImports]


def _recompute_from_answer(answer: Answer):
    """
    Dato un oggetto Answer, ricalcola il LanguageParameter corrispondente
    (lingua = answer.language_id, parametro = answer.question.parameter_id).
    """
    language_id = answer.language_id
    parameter_id = answer.question.parameter_id
    transaction.on_commit(lambda: recompute_and_persist_language_parameter(language_id, parameter_id))


@receiver(post_save, sender=Answer)
def answer_saved_recompute(sender, instance: Answer, **kwargs):
    _recompute_from_answer(instance)


@receiver(post_delete, sender=Answer)
def answer_deleted_recompute(sender, instance: Answer, **kwargs):
    _recompute_from_answer(instance)
