from django import forms
from core.models import Language

# languages_ui/forms.py
from django import forms
from core.models import Language

class LanguageForm(forms.ModelForm):
    class Meta:
        model = Language
        fields = ["id", "name_full", "position", "grp", "isocode", "glottocode", "informant", "supervisor", "assigned_user"]
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "name_full": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1", "inputmode": "numeric"}),
            "grp": forms.TextInput(attrs={"class": "form-control"}),
            "isocode": forms.TextInput(attrs={"class": "form-control"}),
            "glottocode": forms.TextInput(attrs={"class": "form-control"}),
            "informant": forms.TextInput(attrs={"class": "form-control"}),
            "supervisor": forms.TextInput(attrs={"class": "form-control"}),
            "assigned_user": forms.Select(attrs={"class": "form-control", "disabled": "disabled", "aria-readonly": "true"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disabilita a livello form (sicuro lato server)
        self.fields["assigned_user"].disabled = True
        # Aiuto accessibile: spiega dove cambiare l'assegnazione
        self.fields["assigned_user"].help_text = "Modificabile solo dalla pagina di modifica utente (admin)."

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position deve essere un intero positivo (>= 1).")
        return pos

    # Importante: se il campo è disabilitato non torna nei POST,
    # qui forziamo a non cambiarlo mai da questo form.
    def clean_assigned_user(self):
        return getattr(self.instance, "assigned_user", None)



class RejectForm(forms.Form):
    message = forms.CharField(
        label="Messaggio (facoltativo)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
