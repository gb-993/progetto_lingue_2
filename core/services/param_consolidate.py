
from __future__ import annotations
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q

from core.models import (
    Language, ParameterDef, Question, Answer, AnswerStatus, LanguageParameter
)

# Considera valide TUTTE le risposte tranne le REJECTED
ALLOWED_STATUSES = (
    AnswerStatus.PENDING,
    AnswerStatus.WAITING,
    AnswerStatus.APPROVED,
)


def _get_or_create_lp(lang: Language, param: ParameterDef) -> LanguageParameter:
    """
    Garantisce l'esistenza di una riga LanguageParameter per (lang,param).
    Non forza value_orig: può restare NULL (indeterminato).
    """
    obj, _ = LanguageParameter.objects.get_or_create(
        language=lang,
        parameter=param,
        defaults={"value_orig": None, "warning_orig": False},
    )
    return obj


def consolidate_parameter_for_language(
    language: Language,
    parameter: ParameterDef,
) -> Tuple[Optional[str], bool]:
    """
    Calcola il valore ORIGINALE del parametro (+ / - / None) e il warning (solo conflitto).
    Regole:
      - c'è almeno una domanda normale per parametro (vincolo di dominio)
      - se esiste almeno un YES su domanda normale -> valore '+'
        * se contemporaneamente c'è almeno un YES su stop-question -> CONFLITTO: resta '+', warning=True
      - altrimenti, se c'è almeno un YES su stop-question -> valore '-'
      - altrimenti, se TUTTE le domande normali hanno risposta NO -> valore '-'
      - altrimenti (mancano risposte per stabilire 'tutti NO') -> indeterminato => None
    Ritorna: (value, warning)
    """
    # Domande (scope: solo di questo parametro)
    qs_norm = Question.objects.filter(parameter=parameter, is_stop_question=False)
    qs_stop = Question.objects.filter(parameter=parameter, is_stop_question=True)

    # Se per anomalia non ci sono domande normali, NON determiniamo (stato indeterminato)
    if not qs_norm.exists():
        return None, False

    # Risposte della lingua, filtrate per status consentiti
    answers = Answer.objects.filter(
        language=language,
        status__in=ALLOWED_STATUSES,
    ).select_related("question")

    # Partiziona
    norm_answers = [a for a in answers if a.question_id in set(qs_norm.values_list("id", flat=True))]
    stop_answers = [a for a in answers if a.question_id in set(qs_stop.values_list("id", flat=True))]

    # Normalizzatore YES/NO (nel modello è 'yes'|'no')
    def is_yes(a): return (a.response_text or "").lower() == "yes"
    def is_no(a):  return (a.response_text or "").lower() == "no"

    has_norm_yes = any(is_yes(a) for a in norm_answers)
    has_stop_yes = any(is_yes(a) for a in stop_answers)

    # Caso 1: almeno un YES su domanda normale => '+'
    if has_norm_yes:
        warning = has_stop_yes  # conflitto: YES normale + YES stop
        return "+", warning

    # Caso 2: nessun YES normale, ma almeno un YES stop => '-'
    if has_stop_yes:
        return "-", False

    # Caso 3: valuta se TUTTE le normali hanno NO (e sono effettivamente risposte)
    # Recupera l'insieme delle normali
    norm_q_ids = set(qs_norm.values_list("id", flat=True))
    answered_normals = {a.question_id for a in norm_answers}
    # Se non abbiamo copertura completa, è indeterminato (mancano risposte)
    if answered_normals != norm_q_ids:
        return None, False

    # Tutte le normali sono risposte: se tutte NO -> '-', altrimenti indeterminato (teoricamente già coperto)
    if all(is_no(a) for a in norm_answers):
        return "-", False

    # fallback prudenziale (non dovrebbe capitare qui)
    return None, False


@transaction.atomic
def recompute_and_persist_language_parameter(language_id: str, parameter_id: str) -> LanguageParameter:
    """
    Punto di ingresso: ricalcola e salva value_orig/warning_orig di (language, parameter).
    - Se indeterminato => value_orig = NULL, warning_orig=False
    - Se determinato => value_orig in {'+','-'}; warning_orig=True solo nel conflitto
    Ritorna l'oggetto LanguageParameter aggiornato.
    """
        # Se la lingua è stata cancellata (es. delete con cascade), non fare nulla.
    try:
        lang = Language.objects.select_for_update().get(pk=language_id)
    except Language.DoesNotExist:
        return
    lang = Language.objects.select_for_update().get(pk=language_id)
    param = ParameterDef.objects.get(pk=parameter_id)

    lp = _get_or_create_lp(lang, param)
    value, warning = consolidate_parameter_for_language(lang, param)

    lp.value_orig = value  # può essere '+', '-', oppure None
    lp.warning_orig = bool(warning)
    lp.save(update_fields=["value_orig", "warning_orig"])

    return lp
