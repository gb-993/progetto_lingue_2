from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.contrib.auth import authenticate
from core.models import (
    ParameterDef,
    Question,
    Motivation,
    QuestionAllowedMotivation,
)


# =========================
# PARAMETER FORM (ModelForm)
# =========================
from core.services.logic_parser import validate_expression, ParseException

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
            "implicational_condition": forms.TextInput(attrs={"class": "form-control", "placeholder": "(+FGM | +FGA) & -FGK"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position deve essere un intero ≥ 1.")
        return pos

    def clean_implicational_condition(self):
        """
        Regole:
        - consentiti solo token senza spazi tra segno e parametro: +FGM, -FGK, 0ABC
        - operatori: &, |, AND/OR/NOT (case-insensitive)
        - niente spazi tra segno e parametro (anche NBSP, \u00A0)
        """
        raw = (self.cleaned_data.get("implicational_condition") or "").strip()
        if not raw:
            return ""  # condizione vuota = OK

        try:
            # valida con il parser robusto (usa Combine, no spazi interni)
            validate_expression(raw)
        except ParseException as e:
            # Messaggio user-friendly
            raise forms.ValidationError(
                "Condizione invalida. Evita spazi tra segno e parametro (es. usa '-FGK', NON '- FGK'). "
                f"Dettaglio: {e}"
            )
        return raw


# =========================
# QUESTION FORM (ModelForm)
# =========================
class QuestionForm(forms.ModelForm):
    # Scelte template per esempio/visualizzazione
    TEMPLATE_CHOICES = [
        ("", "— nessun template —"),  # lascia questa
        ("linear", "Numerazione semplice (1, 2, 3, ...)"),
        ("paired", "Coppie (1a, 1b, 2a, 2b, ...)"),
        ("decimal", "Decimale (1.1, 1.2, 2.1, 2.2, ...)"),
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

        # === Gestione 'id' in modo robusto ===
        if "id" in self.fields:
            if self.instance and self.instance.pk:
                # In EDIT: l'id deve essere postato ma non modificato
                self.fields["id"].required = False
                self.fields["id"].widget = forms.HiddenInput()  # va dentro hidden_fields
                self.initial["id"] = self.instance.pk
            else:
                # In ADD: l'id deve essere inserito dall'utente
                self.fields["id"].required = True

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



class DeactivateParameterForm(forms.Form):
    """
    Conferma disattivazione parametro:
    - richiede password per re-auth
    - motivo (audit, opzionale ma consigliato)
    """
    password = forms.CharField(
        label="Password amministratore",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "form-control"}),
        required=True,
        help_text="Inserisci la tua password per confermare la disattivazione."
    )
    reason = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        required=False,
        help_text="Motivo della disattivazione (verrà mostrato nei log)."
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get("password") or ""
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            raise forms.ValidationError("Utente non autenticato.")
        # Re-auth semplice: verifica la password dell'utente corrente
        if not user.check_password(pwd):
            raise forms.ValidationError("Password non corretta.")
        return cleaned
