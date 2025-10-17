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
from django import forms
from core.services.logic_parser import validate_expression, ParseException
from core.models import ParameterDef

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
            # NB: non tocco altri campi del modello; se esiste warning_default resta fuori dal Meta come da tuo setup
        ]
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "position": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "step": "1", "inputmode": "numeric"}
            ),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "short_description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "implicational_condition": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "(+FGM | +FGA) & -FGK"
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, can_deactivate: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_deactivate = can_deactivate

        # Campo note modifiche (richiesto solo se ci sono cambi reali in edit)
        self.fields["change_note"] = forms.CharField(
            label="Recap modifiche",
            required=False,
            widget=forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Descrivi sinteticamente COSA è cambiato e PERCHÉ"
            }),
            help_text="Obbligatorio se modifichi qualsiasi campo del parametro.",
        )

        # Se nel template mostri anche warning_default (campo extra non nel Meta), lascia che il template lo gestisca.

    def clean(self):
        cleaned = super().clean()
        instance = getattr(self, "instance", None)
        has_pk = bool(instance and instance.pk)

        # Se NON posso disattivare e l'istanza è attiva, forza comunque is_active=True
        # per evitare flip a False quando il checkbox è disabled (e quindi non postato).
        if has_pk and getattr(self, "can_deactivate", True) is False and instance.is_active:
            cleaned["is_active"] = True

        # Audit: se ci sono modifiche reali (escluso change_note), la nota è obbligatoria
        if has_pk and self.has_changed():
            changed_fields = [f for f in self.changed_data if f != "change_note"]
            note = (cleaned.get("change_note") or "").strip()
            if changed_fields and not note:
                raise forms.ValidationError("Inserisci il recap delle modifiche effettuate.")
        return cleaned

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position deve essere un intero ≥ 1.")
        return pos

    def clean_implicational_condition(self):
        """
        Regole:
        - token senza spazi tra segno e parametro: +FGM, -FGK, 0ABC
        - operatori: &, |, AND/OR/NOT (case-insensitive)
        - niente spazi tra segno e parametro (anche NBSP, \u00A0)
        """
        raw = (self.cleaned_data.get("implicational_condition") or "").strip()
        if not raw:
            return ""  # condizione vuota = OK
        try:
            validate_expression(raw)
        except ParseException as e:
            raise forms.ValidationError(
                "Condizione invalida. Evita spazi tra segno e parametro (es. usa '-FGK', NON '- FGK'). "
                f"Dettaglio: {e}"
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

    # Campo “virtuale” per selezionare le motivazioni consentite (gestito a mano)
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

        # === Gestione 'id'
        if "id" in self.fields:
            if self.instance and self.instance.pk:
                # EDIT: id non modificabile ma deve rientrare nel POST (hidden)
                self.fields["id"].required = False
                self.fields["id"].widget = forms.HiddenInput()
                self.initial["id"] = self.instance.pk
            else:
                # CREATE: id obbligatorio
                self.fields["id"].required = True

        # Pre-selezione motivazioni già collegate
        if self.instance and self.instance.pk:
            self.fields["motivations"].initial = list(
                self.instance.allowed_motivations.values_list("pk", flat=True)
            )

        # >>> Checkbox 'is_stop_question' SOLO in creazione
        if self.instance and self.instance.pk:
            # in edit la rimuoviamo del tutto
            self.fields.pop("is_stop_question", None)

    # --- Salvataggio & sincronizzazione ---

    def save(self, commit=True):
        """
        Salva la Question. Se commit=True, sincronizza subito le motivazioni
        tramite save_m2m(). Se commit=False, la sincronizzazione andrà fatta
        dopo che l'istanza è stata salvata, chiamando form.save_m2m().
        """
        instance = super().save(commit=commit)
        # Se abbiamo già il PK (commit=True oppure l'istanza era già salvata),
        # possiamo sincronizzare immediatamente; altrimenti si farà nel save_m2m().
        if instance.pk and commit:
            self.save_m2m()
        return instance

    def save_m2m(self):
        """
        Override del hook chiamato da ModelForm quando si usa save(commit=False).
        Qui sincronizziamo la tabella ponte QuestionAllowedMotivation in base a
        'motivations' del form.
        """
        instance = getattr(self, "instance", None)
        if not instance or not instance.pk:
            # Nulla da fare se non abbiamo ancora un PK
            return

        # Se il campo non è nel cleaned_data (ad esempio form non valido), esci
        if "motivations" not in self.cleaned_data:
            return

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
