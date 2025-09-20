from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import csv, os

from core.models import (
    User, Glossary, ParameterDef, Language, Question,
    LanguageParameter, Motivation, Answer, Example,
    AnswerMotivation, LanguageParameterEval, AnswerStatus
)

DATA_DIR = "data"  # cambia se tieni i CSV altrove


def parse_bool(v):
    if v is None: return None
    s = str(v).strip().lower()
    return s in ("1","true","t","yes","y","si","s")

def parse_null(v):
    return None if v is None or str(v).strip()=="" else v

def read_csv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

class Command(BaseCommand):
    help = "Importa dati da CSV in data/ in modo idempotente"

    @transaction.atomic
    def handle(self, *args, **opts):
        # 1) USERS
        for r in read_csv("users.csv"):
            email = r["email"].strip().lower()
            user, created = User.objects.get_or_create(email=email, defaults={
                "name": r.get("name",""),
                "surname": r.get("surname",""),
                "role": r.get("role","user"),
                "is_active": parse_bool(r.get("is_active", "1")) if r.get("is_active") is not None else True,
                "is_staff": parse_bool(r.get("is_staff","0")),
                "is_superuser": parse_bool(r.get("is_superuser","0")),
            })
            # set password sempre se fornita
            if parse_null(r.get("password")):
                user.set_password(r["password"])
                user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS("Users ok"))

        # 2) GLOSSARY
        for r in read_csv("glossary.csv"):
            Glossary.objects.update_or_create(
                word=r["word"].strip(),
                defaults={"description": r.get("description","")}
            )
        self.stdout.write(self.style.SUCCESS("Glossary ok"))

        # 3) PARAMETERS
        for r in read_csv("parameters.csv"):
            ParameterDef.objects.update_or_create(
                id=r["id"].strip(),
                defaults={
                    "name": r.get("name",""),
                    "short_description": parse_null(r.get("short_description")),
                    "position": int(r["position"]),
                    "is_active": parse_bool(r.get("is_active","1")),
                    "implicational_condition": parse_null(r.get("implicational_condition")),
                    "warning_default": parse_bool(r.get("warning_default","0")) or False,
                }
            )
        self.stdout.write(self.style.SUCCESS("ParameterDef ok"))

        # 4) LANGUAGES
        users_by_email = {u.email: u.id for u in User.objects.all()}
        for r in read_csv("languages.csv"):
            assigned = users_by_email.get((r.get("assigned_user_email") or "").strip().lower())
            Language.objects.update_or_create(
                id=r["id"].strip(),
                defaults={
                    "name_full": r.get("name_full",""),
                    "position": int(r["position"]),
                    "grp": parse_null(r.get("grp")),
                    "isocode": parse_null(r.get("isocode")),
                    "glottocode": parse_null(r.get("glottocode")),
                    "informant": parse_null(r.get("informant")),
                    "supervisor": parse_null(r.get("supervisor")),
                    "assigned_user_id": assigned,
                }
            )
        self.stdout.write(self.style.SUCCESS("Languages ok"))

        # 5) QUESTIONS
        for r in read_csv("questions.csv"):
            Question.objects.update_or_create(
                id=r["id"].strip(),
                defaults={
                    "parameter_id": r["parameter_id"].strip(),
                    "text": r.get("text",""),
                    "example_yes": parse_null(r.get("example_yes")),
                    "instruction": parse_null(r.get("instruction")),
                    "template_type": parse_null(r.get("template_type")),
                    "is_stop_question": parse_bool(r.get("is_stop_question","0")) or False,
                }
            )
        self.stdout.write(self.style.SUCCESS("Questions ok"))

        # 6) LANGUAGE_PARAMETERS
        for r in read_csv("language_parameters.csv"):
            LanguageParameter.objects.update_or_create(
                language_id=r["language_id"].strip(),
                parameter_id=r["parameter_id"].strip(),
                defaults={
                    "value_orig": r["value_orig"].strip(),  # '+'|'-'
                    "warning_orig": parse_bool(r.get("warning_orig","0")) or False,
                }
            )
        self.stdout.write(self.style.SUCCESS("LanguageParameter ok"))

        # 7) MOTIVATIONS
        for r in read_csv("motivations.csv"):
            Motivation.objects.update_or_create(
                code=r["code"].strip(),
                defaults={"label": r.get("label","")}
            )
        self.stdout.write(self.style.SUCCESS("Motivations ok"))

        # --- OPZIONALI ---

        # ANSWERS
        ans_map = {}
        for r in read_csv("answers.csv"):
            lang = r["language_id"].strip()
            qid  = r["question_id"].strip()
            ans, _ = Answer.objects.update_or_create(
                language_id=lang, question_id=qid,
                defaults={
                    "status": r.get("status","pending"),
                    "modifiable": parse_bool(r.get("modifiable","1")) or True,
                    "response_text": r.get("response_text","yes"),
                    "comments": parse_null(r.get("comments")),
                }
            )
            ans_map[f"{lang}|{qid}"] = ans.id
        if ans_map:
            self.stdout.write(self.style.SUCCESS("Answers ok"))

        # EXAMPLES
        for r in read_csv("examples.csv"):
            key = r["answer_lookup"].strip()  # es. "ita|FGMQ_a"
            ans_id = ans_map.get(key)
            if not ans_id:
                continue
            Example.objects.update_or_create(
                answer_id=ans_id, number=str(r.get("number","")),
                defaults={
                    "textarea": parse_null(r.get("textarea")),
                    "gloss": parse_null(r.get("gloss")),
                    "translation": parse_null(r.get("translation")),
                    "transliteration": parse_null(r.get("transliteration")),
                    "reference": parse_null(r.get("reference")),
                }
            )
        if read_csv("examples.csv"):
            self.stdout.write(self.style.SUCCESS("Examples ok"))

        # ANSWER MOTIVATIONS
        for r in read_csv("answer_motivations.csv"):
            key = r["answer_lookup"].strip()
            ans_id = ans_map.get(key)
            if not ans_id:
                continue
            AnswerMotivation.objects.get_or_create(
                answer_id=ans_id,
                motivation_id=Motivation.objects.get(code=r["motivation_code"].strip()).id
            )
        if read_csv("answer_motivations.csv"):
            self.stdout.write(self.style.SUCCESS("AnswerMotivations ok"))

        # LANGUAGE PARAM EVAL
        for r in read_csv("language_parameter_eval.csv"):
            lp = LanguageParameter.objects.get(
                language_id=r["language_id"].strip(),
                parameter_id=r["parameter_id"].strip()
            )
            LanguageParameterEval.objects.update_or_create(
                language_parameter=lp,
                defaults={
                    "value_eval": r["value_eval"].strip(),  # '+','-','0'
                    "warning_eval": parse_bool(r.get("warning_eval","0")) or False,
                }
            )
        if read_csv("language_parameter_eval.csv"):
            self.stdout.write(self.style.SUCCESS("LanguageParameterEval ok"))

        self.stdout.write(self.style.SUCCESS("Seed da CSV completato."))
