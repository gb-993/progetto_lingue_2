
from django import forms
from core.models import Language



class LanguageForm(forms.ModelForm):
    class Meta:
        model = Language
        fields = ["id", 
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
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "name_full": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1", "inputmode": "numeric"}),
            "top_level_family": forms.TextInput(attrs={"class": "form-control"}),
            "family": forms.TextInput(attrs={"class": "form-control"}),
            "grp": forms.TextInput(attrs={"class": "form-control"}),
            "isocode": forms.TextInput(attrs={"class": "form-control"}),
            "glottocode": forms.TextInput(attrs={"class": "form-control"}),
            "supervisor": forms.TextInput(attrs={"class": "form-control"}),  
            "informant": forms.TextInput(attrs={"class": "form-control"}),         
            "source": forms.TextInput(attrs={"class": "form-control"}),
            "historical_language": forms.CheckboxInput(attrs={"class": ""}),
        }

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position deve essere un intero positivo (>= 1).")
        return pos




class RejectForm(forms.Form):
    message = forms.CharField(
        label="Messaggio (facoltativo)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
