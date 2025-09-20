# parameters_ui/forms.py
from django import forms
from core.models import ParameterDef

class ParameterForm(forms.ModelForm):
    class Meta:
        model = ParameterDef
        fields = ["id", "name", "short_description", "implicational_condition", "is_active", "position"]
        widgets = {
            "id": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "short_description": forms.Textarea(attrs={"class": "form-control"}),
            "implicational_condition": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": 1, "step": 1}),
        }

    # validazione custom del campo "position"
    def clean_position(self):
        p = self.cleaned_data.get("position")
        if p is None or p < 1:
            return 1
        return p