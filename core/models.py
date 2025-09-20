from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.db.models.functions import Lower

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email obbligatoria")
        email = self.normalize_email(email).lower()  # forziamo lowercase
        user = self.model(email=email, **extra_fields)
        user.set_password(password)                  # hash
        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser deve avere is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser deve avere is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (("admin", "Admin"), ("user", "User"))

    email = models.EmailField(unique=True)  # <-- obbligatorio per USERNAME_FIELD
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:  # <-- QUI dentro al modello User
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("email"),
                name="uq_user_email_lower"
            ),
        ]



    def __str__(self):
        return self.email

# =============
# GLOSSARY
# =============
class Glossary(models.Model):
    word = models.CharField(primary_key=True, max_length=255)
    description = models.TextField()


# =============
# LANGUAGE
# =============
class Language(models.Model):
    id = models.CharField(primary_key=True, max_length=10)  # 'ita','en',...
    name_full = models.CharField(max_length=255)
    position = models.IntegerField(unique=True)
    grp = models.CharField(max_length=255, null=True, blank=True)
    isocode = models.CharField(max_length=50, null=True, blank=True)
    glottocode = models.CharField(max_length=50, null=True, blank=True)
    informant = models.CharField(max_length=255, null=True, blank=True)
    supervisor = models.CharField(max_length=255, null=True, blank=True)
    assigned_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="languages"
    )

    class Meta:
        indexes = [
            models.Index(fields=["position"]),
            models.Index(fields=["assigned_user"]),
        ]
        ordering = ["position"]

    def __str__(self):
        return self.name_full


# =======================
# PARAMETER DEFINITIONS
# =======================
# core/models.py
from django.db import models, transaction
from django.db.models import Max, F

class ParameterDef(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    name = models.CharField(max_length=200)
    short_description = models.TextField(blank=True, default="")
    implicational_condition = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField()  # visibile/editabile

    class Meta:
        ordering = ["position"]

    def save(self, *args, **kwargs):
        # Normalizziamo la posizione richiesta
        req_pos = self.position

        with transaction.atomic():
            if self.pk:
                # UPDATE
                old = ParameterDef.objects.get(pk=self.pk)
                if req_pos is None or req_pos < 1:
                    # fallback: append in coda
                    maxpos = ParameterDef.objects.exclude(pk=self.pk).aggregate(m=Max('position'))['m'] or 0
                    req_pos = maxpos + 1

                # limiti massimi (puoi anche ometterlo: andare oltre la coda viene normalizzato)
                maxpos_others = ParameterDef.objects.exclude(pk=self.pk).aggregate(m=Max('position'))['m'] or 0
                if req_pos > maxpos_others + 1:
                    req_pos = maxpos_others + 1

                if old.position != req_pos:
                    if req_pos < old.position:
                        # sposto su: quelli tra [req_pos, old-1] scalano giù (+1)
                        ParameterDef.objects.filter(
                            position__gte=req_pos, position__lt=old.position
                        ).update(position=F('position') + 1)
                    else:
                        # sposto giù: quelli tra [old+1, req_pos] scalano su (-1)
                        ParameterDef.objects.filter(
                            position__gt=old.position, position__lte=req_pos
                        ).update(position=F('position') - 1)
                    self.position = req_pos

            else:
                # CREATE
                if req_pos is None or req_pos < 1:
                    last = ParameterDef.objects.aggregate(m=Max('position'))['m'] or 0
                    req_pos = last + 1
                else:
                    # Creo “spazio”: tutto ciò con pos >= req_pos scala di +1
                    ParameterDef.objects.filter(position__gte=req_pos).update(position=F('position') + 1)
                self.position = req_pos

            super().save(*args, **kwargs)


class Question(models.Model):
    id = models.CharField(primary_key=True, max_length=40)  # 'FGMQ_a'...
    parameter = models.ForeignKey(ParameterDef, on_delete=models.RESTRICT, related_name="questions")
    text = models.TextField()
    example_yes = models.TextField(null=True, blank=True)
    instruction = models.TextField(null=True, blank=True)
    template_type = models.CharField(max_length=50, null=True, blank=True)
    is_stop_question = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["parameter"]),
            models.Index(fields=["parameter", "is_stop_question"]),
        ]


# ==================================
# LANGUAGE_PARAMETER (originali)
# ==================================
class LanguageParameter(models.Model):
    # surrogate PK
    id = models.BigAutoField(primary_key=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name="language_parameters")
    parameter = models.ForeignKey(ParameterDef, on_delete=models.RESTRICT, related_name="language_parameters")
    value_orig = models.CharField(max_length=1)   # '+'|'-'
    warning_orig = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["language", "parameter"], name="uq_lang_param"),
            models.CheckConstraint(check=models.Q(value_orig__in=["+", "-"]), name="ck_value_orig_pm"),
        ]
        indexes = [
            models.Index(fields=["language"]),
            models.Index(fields=["parameter"]),
        ]


# =========
# ANSWER
# =========
class AnswerStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    WAITING = "waiting_for_approval", "Waiting for approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Answer(models.Model):
    id = models.BigAutoField(primary_key=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.RESTRICT, related_name="answers")
    status = models.CharField(max_length=24, choices=AnswerStatus.choices, default=AnswerStatus.PENDING)
    modifiable = models.BooleanField(default=True)
    response_text = models.CharField(max_length=3)  # 'yes'|'no'
    comments = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["language", "question"], name="uq_answer_lang_q"),
            models.CheckConstraint(check=models.Q(response_text__in=["yes", "no"]), name="ck_answer_resp_yesno"),
            models.CheckConstraint(
                check=(
                    models.Q(status__in=[AnswerStatus.PENDING, AnswerStatus.REJECTED], modifiable=True) |
                    models.Q(status__in=[AnswerStatus.WAITING, AnswerStatus.APPROVED], modifiable=False)
                ),
                name="ck_answer_status_modifiable",
            ),
        ]
        indexes = [models.Index(fields=["language"]), models.Index(fields=["question"])]


class Example(models.Model):
    id = models.BigAutoField(primary_key=True)
    number = models.CharField(max_length=50)  # lasciato come testo
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name="examples")
    textarea = models.TextField(null=True, blank=True)
    gloss = models.TextField(null=True, blank=True)
    translation = models.TextField(null=True, blank=True)
    transliteration = models.TextField(null=True, blank=True)
    reference = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["answer"])]


# ============
# MOTIVATION
# ============
class Motivation(models.Model):
    id = models.SmallAutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True)  # es. 'MOT1'
    label = models.CharField(max_length=255)


class AnswerMotivation(models.Model):
    id = models.BigAutoField(primary_key=True)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name="answer_motivations")
    motivation = models.ForeignKey(Motivation, on_delete=models.RESTRICT, related_name="answer_motivations")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["answer", "motivation"], name="uq_answer_motivation"),
        ]
        indexes = [
            models.Index(fields=["answer"]),
            models.Index(fields=["motivation"]),
        ]


# ============================
# EVAL (post-algoritmo)
# ============================
class LanguageParameterEval(models.Model):
    id = models.BigAutoField(primary_key=True)
    language_parameter = models.OneToOneField(
        LanguageParameter, on_delete=models.CASCADE, related_name="eval"
    )
    value_eval = models.CharField(max_length=1)  # '+','-','0'
    warning_eval = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(value_eval__in=["+", "-", "0"]), name="ck_value_eval_pm0"),
        ]


# ============================
# AUDIT / SUBMISSION
# ============================
class Submission(models.Model):
    id = models.BigAutoField(primary_key=True)
    language = models.ForeignKey(Language, on_delete=models.RESTRICT, related_name="submissions")
    submitted_by = models.ForeignKey(User, on_delete=models.RESTRICT, related_name="submissions")
    submitted_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(null=True, blank=True)
    ruleset_version = models.TextField(null=True, blank=True)
    algo_code_hash = models.TextField(null=True, blank=True)
    param_def_checksum = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["language"]),
            models.Index(fields=["submitted_by"]),
            models.Index(fields=["submitted_at"]),
        ]


class SubmissionAnswer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="answers")
    question_code = models.CharField(max_length=40)
    response_text = models.CharField(max_length=3)  # 'yes'|'no'
    comments = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["submission", "question_code"], name="pk_submission_answer"),
            models.CheckConstraint(check=models.Q(response_text__in=["yes", "no"]), name="ck_sub_answer_yesno"),
        ]
        indexes = [models.Index(fields=["submission", "question_code"])]


class SubmissionAnswerMotivation(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="answer_motivations")
    question_code = models.CharField(max_length=40)
    motivation_code = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "question_code", "motivation_code"],
                name="pk_submission_answer_motivation",
            ),
        ]
        indexes = [models.Index(fields=["submission", "question_code"])]


class SubmissionExample(models.Model):
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="examples")
    question_code = models.CharField(max_length=40)
    textarea = models.TextField(null=True, blank=True)
    gloss = models.TextField(null=True, blank=True)
    translation = models.TextField(null=True, blank=True)
    transliteration = models.TextField(null=True, blank=True)
    reference = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["submission", "question_code"])]


class SubmissionParam(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="params")
    parameter_id = models.CharField(max_length=20)
    value_orig = models.CharField(max_length=1)   # '+','-','0'
    warning_orig = models.BooleanField(default=False)
    value_eval = models.CharField(max_length=1)   # '+','-','0'
    warning_eval = models.BooleanField(default=False)
    evaluated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["submission", "parameter_id"], name="pk_submission_param"),
            models.CheckConstraint(check=models.Q(value_orig__in=["+", "-", "0"]), name="ck_sub_param_orig"),
            models.CheckConstraint(check=models.Q(value_eval__in=["+", "-", "0"]), name="ck_sub_param_eval"),
        ]
        indexes = [models.Index(fields=["submission", "parameter_id"])]
