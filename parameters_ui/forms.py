from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from core.models import (
    ParameterDef,
    Question,
    Motivation,
    QuestionAllowedMotivation,
)


# =========================
# PARAMETER FORM (ModelForm)
# =========================
class ParameterForm(forms.ModelForm):
    class Meta:
        model = ParameterDef
        fields = [
            "id",
            "position",
            "name",
            "short_description",
            "implicational_condition",
            "is_active",
        ]
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "position": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "step": "1", "inputmode": "numeric"}
            ),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "short_description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "implicational_condition": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position deve essere un intero ≥ 1.")
        return pos


# =========================
# QUESTION FORM (ModelForm)
# =========================
class QuestionForm(forms.ModelForm):
    # Scelte template per esempio/visualizzazione
    TEMPLATE_CHOICES = [
        ("", "— nessun template —"),
        ("plain", "Plain text"),
        ("glossed", "Glossed line"),
        ("numbered", "Numbered list"),
    ]
    template_type = forms.ChoiceField(choices=TEMPLATE_CHOICES, required=False)

    # Campo “virtuale” per selezionare le motivazioni consentite per questa domanda
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
            "example_yes",
            "template_type",
            "is_stop_question",
        ]
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "text": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "instruction": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "example_yes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_stop_question": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # In edit: congelare l'ID se la domanda esiste (evita problemi con PK)
        if self.instance and self.instance.pk:
            self.fields["id"].disabled = True

        # Pre-seleziona le motivazioni già collegate (via M2M ufficiale)
        if self.instance and self.instance.pk:
            self.fields["motivations"].initial = list(
                self.instance.allowed_motivations.values_list("pk", flat=True)
            )

    def save(self, commit=True):
        """
        Salva la Question e sincronizza la tabella ponte QuestionAllowedMotivation
        in base a 'motivations' inviato dal form.
        """
        instance = super().save(commit=commit)

        if instance.pk and "motivations" in self.cleaned_data:
            selected = set(self.cleaned_data["motivations"].values_list("pk", flat=True))
            existing = set(
                QuestionAllowedMotivation.objects.filter(question=instance)
                .values_list("motivation_id", flat=True)
            )

            # Aggiunte
            to_add = selected - existing
            if to_add:
                QuestionAllowedMotivation.objects.bulk_create(
                    [
                        QuestionAllowedMotivation(question=instance, motivation_id=mid)
                        for mid in to_add
                    ],
                    ignore_conflicts=True,
                )

            # Rimozioni
            to_del = existing - selected
            if to_del:
                QuestionAllowedMotivation.objects.filter(
                    question=instance, motivation_id__in=to_del
                ).delete()

        return instance


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
        "template_type",
        "is_stop_question",
    ],
    extra=1,
    can_delete=True,
)
