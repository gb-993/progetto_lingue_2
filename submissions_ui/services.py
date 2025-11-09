
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from core.models import (
    Language, User, Submission, SubmissionAnswer, SubmissionAnswerMotivation,
    SubmissionExample, SubmissionParam, Answer, AnswerMotivation, Example,
    LanguageParameter, LanguageParameterEval, ParameterDef, Question
)


MAX_PER_LANGUAGE = getattr(settings, "SUBMISSIONS_MAX_PER_LANGUAGE", 10)

@dataclass
class SnapshotResult:
    submission: Submission
    pruned_count: int

def create_language_submission(language: Language, submitted_by: User, note: str | None = None) -> SnapshotResult:
    """
    Crea uno snapshot 'full' per una lingua.
    - Copia Answers (yes/no + comments)
    - Copia Motivations collegate alle Answers
    - Copia Examples collegati alle Answers
    - Copia Parametri consolidati (orig/eval)
    Esegue pruning per tenere al massimo N submissions per lingua.
    """
    now = timezone.now()
    with transaction.atomic():
        sub = Submission.objects.create(
            language=language,
            submitted_by=submitted_by,
            submitted_at=now,
            note=note or "",
            
        )

        
        answers = (
            Answer.objects
            .filter(language=language)
            .select_related("question")
            .prefetch_related("answer_motivations__motivation", "examples")
        )

        
        sub_answers = []
        for a in answers:
            sub_answers.append(SubmissionAnswer(
                submission=sub,
                question_code=a.question_id,
                response_text=a.response_text,
                comments=a.comments or "",
            ))
        SubmissionAnswer.objects.bulk_create(sub_answers, ignore_conflicts=False)

        
        sub_mots = []
        for a in answers:
            for am in a.answer_motivations.all():
                sub_mots.append(SubmissionAnswerMotivation(
                    submission=sub,
                    question_code=a.question_id,
                    motivation_code=am.motivation.code,
                ))
        if sub_mots:
            SubmissionAnswerMotivation.objects.bulk_create(sub_mots, ignore_conflicts=False)

        
        sub_ex = []
        for a in answers:
            for ex in a.examples.all():
                sub_ex.append(SubmissionExample(
                    submission=sub,
                    question_code=a.question_id,
                    textarea=ex.textarea or "",
                    gloss=ex.gloss or "",
                    translation=ex.translation or "",
                    transliteration=ex.transliteration or "",
                    reference=ex.reference or "",
                ))
        if sub_ex:
            SubmissionExample.objects.bulk_create(sub_ex, ignore_conflicts=False)

        
        
        lparams = (
            LanguageParameter.objects
            .filter(language=language)
            .select_related("parameter", "eval")
        )

        sub_params = []
        for lp in lparams:
            eval_obj = getattr(lp, "eval", None)
            sub_params.append(SubmissionParam(
                submission=sub,
                parameter_id=lp.parameter_id,
                value_orig=lp.value_orig,                
                warning_orig=lp.warning_orig,
                value_eval=(eval_obj.value_eval if eval_obj else "0"),
                warning_eval=(eval_obj.warning_eval if eval_obj else False),
                evaluated_at=now,
            ))
        if sub_params:
            SubmissionParam.objects.bulk_create(sub_params, ignore_conflicts=False)

        
        pruned = 0
        if MAX_PER_LANGUAGE and MAX_PER_LANGUAGE > 0:
            qs_old = (Submission.objects
                      .filter(language=language)
                      .order_by("-submitted_at", "-id")
                      .values_list("id", flat=True))
            ids_to_keep = list(qs_old[:MAX_PER_LANGUAGE])
            if len(ids_to_keep) < qs_old.count():
                to_delete = Submission.objects.filter(language=language).exclude(id__in=ids_to_keep)
                pruned = to_delete.count()
                to_delete.delete()

        return SnapshotResult(submission=sub, pruned_count=pruned)
