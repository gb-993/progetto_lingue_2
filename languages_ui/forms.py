
from django import forms
from core.models import Language



class LanguageForm(forms.ModelForm):
    class Meta:
        model = Language
        fields = [
            "id",
            "name_full",
            "position",
            "top_level_family",
            "family",
            "grp",
            "isocode",
            "glottocode",
            "supervisor",
            "informant",
            "source",
            "historical_language",
        ]

        
        labels = {
            "id": "Id",  
            "name_full": "Name",
            "position": "Position",
            "top_level_family": "Top-level family",
            "family": "Family",
            "grp": "Group",
            "isocode": "ISO code",
            "glottocode": "Glottocode",
            "supervisor": "Supervisor",
            "informant": "Informant",
            "source": "Source",
            "historical_language": "Historical language",
        }

        
        widgets = {
            "id": forms.TextInput(attrs={
                "class": "form-control",
                "autocomplete": "off",
                "placeholder": "Language ID",
            }),
            "name_full": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Full language name",
            }),
            "position": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "step": "1",
                "inputmode": "numeric",
                "placeholder": "Order / position",
            }),
            "top_level_family": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Top-level family",
            }),
            "family": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Family (more specific)",
            }),
            "grp": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Group",
            }),
            "isocode": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "ISO code",
            }),
            "glottocode": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Glottocode",
            }),
            "supervisor": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Supervisor",
            }),
            "informant": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Informant",
            }),
            "source": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Source / reference",
            }),
            "historical_language": forms.CheckboxInput(attrs={
                "class": "",
                
            }),
        }

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position must be a positive integer (>= 1).")
        return pos





class RejectForm(forms.Form):
    message = forms.CharField(
        label="Message (optional)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
