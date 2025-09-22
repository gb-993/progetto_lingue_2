from django import forms
from core.models import ParameterDef
from django.core.exceptions import ValidationError

class ParameterForm(forms.ModelForm):
    class Meta:
        model = ParameterDef
        fields = ["id", "position", "name", "short_description", "implicational_condition", "is_active"]

        # per CSS
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "1", "inputmode": "numeric"}),
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

