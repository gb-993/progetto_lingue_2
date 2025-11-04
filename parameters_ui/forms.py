from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate

from core.models import (
    ParameterDef,
    Question,
    Motivation,
    QuestionAllowedMotivation,
    ParamSchema,
    ParamType,
)
from core.services.logic_parser import validate_expression, ParseException


# =========================
# PARAMETER FORM (ModelForm)
# =========================
class ParameterForm(forms.ModelForm):
    schema = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Schema",
    )
    param_type = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Type",
    )

    class Meta:
        model = ParameterDef
        fields = [
            "id",
            "position",
            "name",
            "short_description",
            "implicational_condition",
            "is_active",
            "schema",
            "param_type",
        ]
        labels = {
        "id": "Label",   
        "position": "Position",
        "name": "Name",
        "short_description": "Short description",
        "implicational_condition": "Implicational condition",
        "is_active": "Active",
        "schema": "Schema",
        "param_type": "Type",
        }

        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1", "inputmode": "numeric"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "short_description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "implicational_condition": forms.TextInput(attrs={"class": "form-control", "placeholder": "(+FGM | +FGA) & -FGK"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, can_deactivate: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_deactivate = can_deactivate

        # Popola le scelte dai lookup
        schema_labels = list(ParamSchema.objects.order_by("label").values_list("label", flat=True))
        type_labels   = list(ParamType.objects.order_by("label").values_list("label", flat=True))

        schema_choices = [("", "— select schema —")] + [(s, s) for s in schema_labels]
        type_choices   = [("", "— select type —")]   + [(t, t) for t in type_labels]

        # Se il record ha valori legacy non più in lista, aggiungili per mostrare e salvare
        inst = getattr(self, "instance", None)
        if inst and inst.pk:
            if inst.schema and inst.schema not in {c for c, _ in schema_choices}:
                schema_choices.insert(1, (inst.schema, f"{inst.schema} (legacy)"))
            if inst.param_type and inst.param_type not in {c for c, _ in type_choices}:
                type_choices.insert(1, (inst.param_type, f"{inst.param_type} (legacy)"))

        self.fields["schema"].choices = schema_choices
        self.fields["param_type"].choices = type_choices

        # Campo "change_note" se non già presente
        if "change_note" not in self.fields:
            self.fields["change_note"] = forms.CharField(
                label="Brief summary of changes",
                required=False,
                widget=forms.Textarea(attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Describe the changes you made to this parameter..."
                }),
                help_text="Mandatory if you changed any field.",
            )

    def clean(self):
        cleaned = super().clean()
        instance = getattr(self, "instance", None)
        has_pk = bool(instance and instance.pk)

        if has_pk and getattr(self, "can_deactivate", True) is False and instance.is_active:
            cleaned["is_active"] = True

        if has_pk and self.has_changed():
            changed_fields = [f for f in self.changed_data if f != "change_note"]
            note = (cleaned.get("change_note") or "").strip()
            if changed_fields and not note:
                raise forms.ValidationError("Insert recap of changes made to this parameter.")
        return cleaned

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position must be an integer ≥ 1.")
        return pos

    def clean_implicational_condition(self):

        raw = (self.cleaned_data.get("implicational_condition") or "").strip()
        if not raw:
            return "" 
        try:
            validate_expression(raw)
        except ParseException as e:
            raise forms.ValidationError(
                "Invalid condition. Don't put spaces between sign and parameter (es. usa '-FGK', NON '- FGK'). "
                f"Details: {e}"
            )
        return raw


# =========================
# QUESTION FORM (ModelForm)
# =========================
class QuestionForm(forms.ModelForm):
    # Scelte per la presentazione/numero degli esempi
    TEMPLATE_CHOICES = [
        ("", "— nessun template —"),
        ("linear", "Numerazione semplice (1, 2, 3, ...)"),
        ("paired", "Coppie (1a, 1b, 2a, 2b, ...)"),
        ("decimal", "Decimale (1.1, 1.2, 2.1, 2.2, ...)"),
    ]
    template_type = forms.ChoiceField(choices=TEMPLATE_CHOICES, required=False)

    motivations = forms.ModelMultipleChoiceField(
        queryset=Motivation.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Motivazioni disponibili per NO",
        help_text="Seleziona le motivazioni che l'utente potrà scegliere quando risponde NO a questa domanda.",
    )

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "instruction",
            "help_info",
            "example_yes",
            "instruction_yes", 
            "template_type",
            "is_stop_question",
        ]
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "text": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "instruction": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "instruction_yes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "help_info": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "example_yes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_stop_question": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "id" in self.fields:
            if self.instance and self.instance.pk:
                self.fields["id"].required = False
                self.fields["id"].widget = forms.HiddenInput()
                self.initial["id"] = self.instance.pk
            else:
                self.fields["id"].required = True

        if self.instance and self.instance.pk:
            self.fields["motivations"].initial = list(
                self.instance.allowed_motivations.values_list("pk", flat=True)
            )

        if self.instance and self.instance.pk:
            self.fields.pop("is_stop_question", None)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if instance.pk and commit:
            self.save_m2m()
        return instance

    def save_m2m(self):
        instance = getattr(self, "instance", None)
        if not instance or not instance.pk:
            return
        if "motivations" not in self.cleaned_data:
            return

        selected = set(self.cleaned_data["motivations"].values_list("pk", flat=True))
        existing = set(
            QuestionAllowedMotivation.objects.filter(question=instance)
            .values_list("motivation_id", flat=True)
        )

        # aggiunte
        to_add = selected - existing
        if to_add:
            QuestionAllowedMotivation.objects.bulk_create(
                [
                    QuestionAllowedMotivation(question=instance, motivation_id=mid)
                    for mid in to_add
                ],
                ignore_conflicts=True,
            )

        # rimozioni
        to_del = existing - selected
        if to_del:
            QuestionAllowedMotivation.objects.filter(
                question=instance, motivation_id__in=to_del
            ).delete()


# =========================
# INLINE FORMSET Question <- ParameterDef
# =========================
QuestionFormSet = inlineformset_factory(
    parent_model=ParameterDef,
    model=Question,
    form=QuestionForm,
    fields=[
        "id",
        "text",
        "instruction",
        "example_yes",
        "instruction_yes",
        "template_type",
        "is_stop_question",
    ],
    extra=1,
    can_delete=True,
)


class DeactivateParameterForm(forms.Form):

    password = forms.CharField(
        label="Admin Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "form-control"}),
        required=True,
        help_text="Insert your password to deactivate."
    )
    reason = forms.CharField(
        label="Motivations",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        required=False,
        help_text="Motivation of deletion."
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get("password") or ""
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            raise forms.ValidationError("User not authenticated.")
        if not user.check_password(pwd):
            raise forms.ValidationError("Incorrect password.")
        return cleaned
