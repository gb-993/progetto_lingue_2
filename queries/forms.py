from django import forms
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from core.models import (
    User, Language, ParameterDef, Question, Answer, Example,
    Motivation, AnswerMotivation, QuestionAllowedMotivation,
    LanguageParameter,
)

# Eval opzionale (se il modello non esiste, disabilita i campi correlati)
try:
    from core.models import LanguageParameterEval
    HAS_EVAL = True
except Exception:
    LanguageParameterEval = None  # type: ignore
    HAS_EVAL = False

DATASET_CHOICES = [
    ("user",      _("Utenti")),
    ("language",  _("Lingue")),
    ("question",  _("Domande")),
    ("answer",    _("Risposte")),
    ("parameter", _("Parametri")),
    ("example",   _("Esempi")),
    ("motivation",_("Motivazioni")),
    ("langparam", _("Valori parametri")),
]

YN = [("", "—"), ("1", _("Sì")), ("0", _("No"))]

class BaseFilterForm(forms.Form):
    dataset = forms.ChoiceField(choices=DATASET_CHOICES, required=True, label=_("Dataset"))
    q_name  = forms.CharField(
        required=False, label=_("Cerca nome/testo"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Cerca per nome/testo")})
    )
    page = forms.IntegerField(required=False, widget=forms.HiddenInput)

# -------- User
ROLE_CHOICES = [
    ("", "—"),
    ("admin", "admin"),
    ("linguist", "linguist"),
    ("user", "user"),
    ("staff", "staff"),  # se usi un role custom, adatta
]

class UserFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("user", _("Utenti"))])
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=False, label=_("Ruolo"), widget=forms.Select(attrs={"class": "form-select"}))
    is_active = forms.ChoiceField(choices=YN, required=False, label=_("Attivo?"), widget=forms.Select(attrs={"class": "form-select"}))
    is_staff  = forms.ChoiceField(choices=YN, required=False, label=_("Staff?"),  widget=forms.Select(attrs={"class": "form-select"}))
    has_assigned_languages = forms.ChoiceField(choices=YN, required=False, label=_("Ha lingue assegnate (FK)?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_m2m_languages      = forms.ChoiceField(choices=YN, required=False, label=_("Ha lingue (M2M)?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_answers_on_languages = forms.ChoiceField(choices=YN, required=False, label=_("Lingue dell’utente con risposte?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_submissions = forms.ChoiceField(choices=YN, required=False, label=_("Ha submission?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- Language
class LanguageFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("language", _("Lingue"))])
    grp = forms.CharField(required=False, label=_("Gruppo"), widget=forms.TextInput(attrs={"class": "form-control"}))
    isocode = forms.CharField(required=False, label=_("ISO"), widget=forms.TextInput(attrs={"class": "form-control"}))
    glottocode = forms.CharField(required=False, label=_("Glottocode"), widget=forms.TextInput(attrs={"class": "form-control"}))
    assigned_user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by("email"),
        required=False, label=_("Assegnata a"),
        widget=forms.Select(attrs={"class": "form-select"})
    )
    has_answers = forms.ChoiceField(choices=YN, required=False, label=_("Ha risposte?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_params  = forms.ChoiceField(choices=YN, required=False, label=_("Ha parametri valorizzati?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- Parameter
class ParameterFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("parameter", _("Parametri"))])
    is_active = forms.ChoiceField(choices=YN, required=False, label=_("Attivo?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_questions = forms.ChoiceField(choices=YN, required=False, label=_("Ha domande?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- Question
class QuestionFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("question", _("Domande"))])
    parameter = forms.ModelChoiceField(queryset=ParameterDef.objects.all().order_by("position"),
                                       required=False, label=_("Parametro"),
                                       widget=forms.Select(attrs={"class": "form-select"}))
    is_stop = forms.ChoiceField(choices=YN, required=False, label=_("Stop question?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_answers = forms.ChoiceField(choices=YN, required=False, label=_("Ha risposte?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_allowed_motiv = forms.ChoiceField(choices=YN, required=False, label=_("Ha motivazioni consentite?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- Answer
class AnswerFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("answer", _("Risposte"))])
    language = forms.ModelChoiceField(queryset=Language.objects.all().order_by("position"),
                                      required=False, label=_("Lingua"),
                                      widget=forms.Select(attrs={"class": "form-select"}))
    question = forms.ModelChoiceField(queryset=Question.objects.all().order_by("id"),
                                      required=False, label=_("Domanda"),
                                      widget=forms.Select(attrs={"class": "form-select"}))
    response_text = forms.ChoiceField(choices=[("", "—"), ("yes", "YES"), ("no", "NO")],
                                      required=False, label=_("Risposta"),
                                      widget=forms.Select(attrs={"class": "form-select"}))
    status = forms.ChoiceField(choices=[("", "—"), ("pending","pending"), ("waiting","waiting"), ("approved","approved"), ("rejected","rejected")],
                               required=False, label=_("Stato"),
                               widget=forms.Select(attrs={"class": "form-select"}))
    has_examples    = forms.ChoiceField(choices=YN, required=False, label=_("Ha esempi?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_motivations = forms.ChoiceField(choices=YN, required=False, label=_("Ha motivazioni?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- Example
class ExampleFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("example", _("Esempi"))])
    has_gloss = forms.ChoiceField(choices=YN, required=False, label=_("Gloss presente?"), widget=forms.Select(attrs={"class": "form-select"}))
    has_translation = forms.ChoiceField(choices=YN, required=False, label=_("Traduzione presente?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- Motivation
class MotivationFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("motivation", _("Motivazioni"))])
    used_in_answers = forms.ChoiceField(choices=YN, required=False, label=_("Usata in risposte?"), widget=forms.Select(attrs={"class": "form-select"}))
    allowed_in_questions = forms.ChoiceField(choices=YN, required=False, label=_("Consentita da domande?"), widget=forms.Select(attrs={"class": "form-select"}))

# -------- LanguageParameter (orig/eval)
VAL_ORIG = [("", "—"), ("+", "+"), ("-", "-"), ("null", _("Indeterminato"))]
VAL_EVAL = [("", "—"), ("+", "+"), ("-", "-"), ("0", "0")]

class LangParamFilterForm(BaseFilterForm):
    dataset = forms.ChoiceField(choices=[("langparam", _("Valori parametri"))])
    parameter = forms.ModelChoiceField(queryset=ParameterDef.objects.all().order_by("position"),
                                       required=False, label=_("Parametro"),
                                       widget=forms.Select(attrs={"class": "form-select"}))
    value_orig = forms.ChoiceField(choices=VAL_ORIG, required=False, label=_("Valore orig"), widget=forms.Select(attrs={"class": "form-select"}))
    warning_orig = forms.ChoiceField(choices=YN, required=False, label=_("Warning orig?"), widget=forms.Select(attrs={"class": "form-select"}))
    if HAS_EVAL:
        value_eval = forms.ChoiceField(choices=VAL_EVAL, required=False, label=_("Valore eval"), widget=forms.Select(attrs={"class": "form-select"}))
        warning_eval = forms.ChoiceField(choices=YN, required=False, label=_("Warning eval?"), widget=forms.Select(attrs={"class": "form-select"}))
