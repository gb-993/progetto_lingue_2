from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models, transaction, connection
from django.db.models.functions import Lower
from django.utils import timezone
from django.db.models import Q, F, Max, UniqueConstraint, Deferrable
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.conf import settings


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email obbligatoria")
        email = self.normalize_email(email).lower()  # forza lowercase
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

    m2m_languages  = models.ManyToManyField(
        "core.Language",      # riferimento per stringa, niente import
        blank=True,
        related_name="users"  # es: language.users.all()
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:  
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
from django.db import models, transaction, connection
from django.db.models import F, Max, UniqueConstraint, Deferrable
from django.core.exceptions import ObjectDoesNotExist, ValidationError

class Language(models.Model):
    id = models.CharField(primary_key=True, max_length=10)  # 'ita','en',...
    name_full = models.CharField(max_length=255)

    position = models.PositiveIntegerField()

    grp = models.CharField(max_length=255, null=True, blank=True)
    isocode = models.CharField(max_length=50, null=True, blank=True)
    glottocode = models.CharField(max_length=50, null=True, blank=True)
    informant = models.CharField(max_length=255, null=True, blank=True)
    supervisor = models.CharField(max_length=255, null=True, blank=True)
    assigned_user = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="languages"
    )

    class Meta:
        indexes = [
            models.Index(fields=["position"]),
            models.Index(fields=["assigned_user"]),
        ]
        ordering = ["position"]
        constraints = [
            UniqueConstraint(
                fields=["position"],
                name="uniq_language_position_deferrable",
                deferrable=Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        return self.name_full

    # Advisory lock per serializzare gli shift 
    def _advisory_lock(self):
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s);", [123456789])

    def save(self, *args, **kwargs):
        """
        Mantiene 'position' univoca e compatta:
        - INSERT senza position -> append in coda (max+1)
        - INSERT con position N -> shifta (>=N) di +1 e inserisce a N
        - UPDATE old->new:
            * se new > old: decrementa (old, new] di 1
            * se new < old: incrementa [new, old) di 1
        """
        is_new = self._state.adding or self.pk is None

        with transaction.atomic():
            self._advisory_lock()

            if is_new:
                # Se manca una position valida, append in coda
                if not self.position or self.position < 1:
                    max_pos = type(self).objects.aggregate(m=Max("position"))["m"] or 0
                    self.position = max_pos + 1
                    return super().save(*args, **kwargs)

                # Inserisco a 'position' richiesta e shifto le successive
                type(self).objects.filter(position__gte=self.position).update(position=F("position") + 1)
                return super().save(*args, **kwargs)

            # UPDATE
            try:
                old = type(self).objects.get(pk=self.pk)
            except ObjectDoesNotExist:
                # oggetto non esiste più, salvo semplice
                return super().save(*args, **kwargs)

            old_pos = old.position
            new_pos = self.position or old_pos

            if new_pos == old_pos:
                return super().save(*args, **kwargs)

            if new_pos > old_pos:
                # sposto in basso: le righe tra (old_pos, new_pos] scalano -1
                type(self).objects.filter(
                    position__gt=old_pos,
                    position__lte=new_pos
                ).exclude(pk=self.pk).update(position=F("position") - 1)
            else:
                # sposto in alto: le righe tra [new_pos, old_pos) scalano +1
                type(self).objects.filter(
                    position__gte=new_pos,
                    position__lt=old_pos
                ).exclude(pk=self.pk).update(position=F("position") + 1)

            return super().save(*args, **kwargs)

    # Evita che la validazione lato Django blocchi per 'position' (ci pensa il DB deferrable)
    def validate_unique(self, exclude=None):
        ex = set(exclude or [])
        ex.add("position")
        super().validate_unique(exclude=ex)

    def validate_constraints(self, exclude=None):
        try:
            super().validate_constraints(exclude=exclude)
        except ValidationError as e:
            error_dict = getattr(e, "error_dict", None)
            error_list = getattr(e, "error_list", None)

            if error_dict is not None:
                error_dict.pop("position", None)
                if error_dict:
                    raise ValidationError(error_dict)
                return

            if error_list is not None:
                filtered = []
                for err in error_list:
                    msg = str(err)
                    if "uniq_language_position_deferrable" in msg or "Position" in msg:
                        continue
                    filtered.append(err)
                if filtered:
                    raise ValidationError(filtered)
                return
            raise



# =======================
# PARAMETER DEFINITIONS
# =======================


class ParameterDef(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    name = models.CharField(max_length=200)
    short_description = models.TextField(blank=True, default="")
    implicational_condition = models.CharField(max_length=255, null=True, blank=True, default="")
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField()
    warning_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["position"]
        constraints = [
            UniqueConstraint(
                fields=["position"],
                name="uniq_parameterdef_position_deferrable",
                deferrable=Deferrable.DEFERRED,
            ),
        ]

    def _advisory_lock(self):
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s);", [987654321])

    def save(self, *args, **kwargs):
        is_new = self._state.adding or self.pk is None
        with transaction.atomic():
            self._advisory_lock()

            if is_new:
                if not self.position:  
                    max_pos = type(self).objects.aggregate(m=Max("position"))["m"] or 0
                    self.position = max_pos + 1
                    return super().save(*args, **kwargs)

                type(self).objects.filter(position__gte=self.position)\
                    .update(position=F("position") + 1)
                return super().save(*args, **kwargs)

            # UPDATE
            try:
                old = type(self).objects.get(pk=self.pk)
            except ObjectDoesNotExist:
                return super().save(*args, **kwargs)

            old_pos = old.position
            new_pos = self.position or old_pos

            if new_pos == old_pos:
                return super().save(*args, **kwargs)

            if new_pos > old_pos:
                type(self).objects.filter(
                    position__gt=old_pos,
                    position__lte=new_pos
                ).exclude(pk=self.pk).update(position=F("position") - 1)
            else:
                type(self).objects.filter(
                    position__gte=new_pos,
                    position__lt=old_pos
                ).exclude(pk=self.pk).update(position=F("position") + 1)

            return super().save(*args, **kwargs)

    def validate_unique(self, exclude=None):
        ex = set(exclude or [])
        ex.add("position")
        super().validate_unique(exclude=ex)

    def validate_constraints(self, exclude=None):
        try:
            super().validate_constraints(exclude=exclude)
        except ValidationError as e:
            error_dict = getattr(e, "error_dict", None)
            error_list = getattr(e, "error_list", None)

            if error_dict is not None:
                error_dict.pop("position", None)
                if error_dict:
                    raise ValidationError(error_dict)
                return

            if error_list is not None:
                filtered = []
                for err in error_list:
                    msg = str(err)
                    if "uniq_parameterdef_position_deferrable" in msg or "Position" in msg:
                        continue
                    filtered.append(err)
                if filtered:
                    raise ValidationError(filtered)
                return
            raise


class ParameterChangeLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    parameter = models.ForeignKey(ParameterDef, on_delete=models.CASCADE, related_name="change_logs")
    recap = models.TextField()  # obbligatorio
    diff = models.JSONField(default=dict, blank=True)  # {campo: {"old":..., "new":...}}
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="parameter_change_logs")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["changed_at"]),
            models.Index(fields=["parameter"]),
            models.Index(fields=["changed_by"]),
        ]

    def __str__(self):
        who = self.changed_by.email if self.changed_by else "unknown"
        return f"{self.parameter_id} by {who} @ {self.changed_at:%Y-%m-%d %H:%M}"



class Question(models.Model):
    id = models.CharField(primary_key=True, max_length=40)  # es. 'FGMQ_a'
    parameter = models.ForeignKey(
        ParameterDef,
        on_delete=models.RESTRICT,
        related_name="questions"
    )
    text = models.TextField()
    example_yes = models.TextField(null=True, blank=True)
    instruction = models.TextField(null=True, blank=True)
    template_type = models.CharField(max_length=50, null=True, blank=True)
    is_stop_question = models.BooleanField(default=False)
    help_info = models.TextField(null=True, blank=True)

    # M2M ufficiale
    allowed_motivations = models.ManyToManyField(
        "core.Motivation",
        through="core.QuestionAllowedMotivation",
        related_name="questions_allowed",
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["parameter"]),
            models.Index(fields=["parameter", "is_stop_question"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.parameter_id}"



class LanguageReview(models.Model):
    DECISION_CHOICES = [
        ("approve", "Approve"),
        ("reject", "Reject"),
    ]
    language = models.ForeignKey("Language", on_delete=models.CASCADE, related_name="reviews")
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES)
    message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.language_id} {self.decision} @ {self.created_at:%Y-%m-%d %H:%M}"

# ===============================================
# LANGUAGE_PARAMETER (originali per ogni lingua)
# ===============================================
class LanguageParameter(models.Model):
    # surrogate PK
    id = models.BigAutoField(primary_key=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name="language_parameters")
    parameter = models.ForeignKey(ParameterDef, on_delete=models.RESTRICT, related_name="language_parameters")

    # MODIFICA: permettiamo NULL per rappresentare "indeterminato"
    value_orig = models.CharField(max_length=1, null=True, blank=True)   # '+','-' oppure NULL (indeterminato)
    warning_orig = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["language", "parameter"], name="uq_lang_param"),

            # MODIFICA: aggiorniamo il check per consentire anche NULL
            models.CheckConstraint(
                check=(models.Q(value_orig__in=["+", "-"]) | models.Q(value_orig__isnull=True)),
                name="ck_value_orig_pm_or_null",
            ),
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
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["language", "question"], name="uq_answer_lang_q"),
            models.CheckConstraint(check=models.Q(response_text__in=["yes", "no"]), name="ck_answer_resp_yesno"),
            models.CheckConstraint(
                check=(
                    models.Q(status__in=[AnswerStatus.PENDING], modifiable=True) |
                    models.Q(status__in=[AnswerStatus.WAITING, AnswerStatus.APPROVED,AnswerStatus.REJECTED], modifiable=False)
                ),
                name="ck_answer_status_modifiable",
            ),
        ]
        indexes = [models.Index(fields=["language"]), models.Index(fields=["question"])]

        
class ParameterReviewFlag(models.Model):
    """
    Flag personale (per-utente) per segnare un parametro di una lingua come "da rivedere".
    Unique: (language, parameter, user)
    """
    language = models.ForeignKey("Language", on_delete=models.CASCADE, related_name="review_flags")
    parameter = models.ForeignKey("ParameterDef", on_delete=models.CASCADE, related_name="review_flags")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_flags")
    flag = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["language", "parameter", "user"],
                name="uq_reviewflag_lang_param_user"
            )
        ]
        indexes = [
            models.Index(fields=["language", "user"]),
            models.Index(fields=["parameter"]),
        ]

    def __str__(self) -> str:
        return f"{self.language_id}-{self.parameter_id} by {self.user_id}: {self.flag}"


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

class QuestionAllowedMotivation(models.Model):
    id = models.BigAutoField(primary_key=True)

    question = models.ForeignKey(
        "core.Question",
        on_delete=models.CASCADE,
        related_name="allowed_motivation_links"  # <-- prima era "allowed_motivations"
    )
    motivation = models.ForeignKey(
        "core.Motivation",
        on_delete=models.RESTRICT,
        related_name="allowed_for_questions"
    )
    position = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["question", "motivation"], name="uq_question_allowed_motivation"),
        ]
        indexes = [
            models.Index(fields=["question"]),
            models.Index(fields=["motivation"]),
            models.Index(fields=["question", "position"]),
        ]

# Unisce Answer alle sue Motivation (M2M tramite tabella esplicita)
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
        LanguageParameter,
        on_delete=models.CASCADE,
        related_name="eval",
    )

    # Ora può essere NULL per rappresentare "indeterminato" (da mostrare vuoto in UI)
    value_eval = models.CharField(
        max_length=1,
        null=True,
        blank=True,
        choices=(('+', '+'), ('-', '-'), ('0', '0')),
        help_text="Valore valutato dal DAG: '+', '-', '0' oppure NULL (indeterminato/da mostrare vuoto).",
    )

    warning_eval = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # Nuovo vincolo: consente '+', '-', '0' OPPURE NULL
            models.CheckConstraint(
                name="ck_value_eval_pm0_or_null",
                check=Q(value_eval__in=['+', '-', '0']) | Q(value_eval__isnull=True),
            ),
        ]

    def __str__(self):
        return f"Eval({self.language_parameter_id}): {self.value_eval or 'NULL'}{' !' if self.warning_eval else ''}"


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
    value_orig = models.CharField(max_length=1,null=True, blank=True)   
    warning_orig = models.BooleanField(default=False)
    value_eval = models.CharField(max_length=1, null=True, blank=True, choices=(('+', '+'), ('-', '-'), ('0', '0')),)   # '+','-','0'
    warning_eval = models.BooleanField(default=False)
    evaluated_at = models.DateTimeField(default=timezone.now)

class Meta:
        constraints = [
            models.UniqueConstraint(fields=["submission", "parameter_id"], name="pk_submission_param"),
            models.CheckConstraint(
                check=models.Q(value_orig__in=["+", "-", "0"]) | models.Q(value_orig__isnull=True),
                name="ck_sub_param_orig",
            ),
            models.CheckConstraint(
                check=models.Q(value_eval__in=["+", "-", "0"]) | models.Q(value_eval__isnull=True),
                name="ck_sub_param_eval",
            ),
        ]
        indexes = [models.Index(fields=["submission", "parameter_id"])]