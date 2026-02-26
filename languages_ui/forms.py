
from django import forms
from core.models import Language



class LanguageForm(forms.ModelForm):
    class Meta:
        model = Language
        fields = [
            "id",
            "name_full",
            "top_level_family",
            "family",
            "grp",
            "isocode",
            "glottocode",
            "supervisor",
            "informant",
            "source",
            "historical_language",
            "latitude",
            "longitude",
        ]

        
        labels = {
            "id": "Id",  
            "name_full": "Name",
            "top_level_family": "Top-level family",
            "family": "Family",
            "grp": "Group",
            "isocode": "ISO code",
            "glottocode": "Glottocode",
            "supervisor": "Supervisor",
            "informant": "Informant",
            "source": "Source",
            "historical_language": "Historical language",
            "latitude": "Latitude",
            "longitude": "Longitude",
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
            "latitude": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.000001",
                "inputmode": "decimal",
                "placeholder": "e.g., 45.4642 (range: -90 to 90)",
                "min": "-90",
                "max": "90",
                "title": "Latitude must be between -90 and 90",
            }),
            "longitude": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.000001",
                "inputmode": "decimal",
                "placeholder": "e.g., 9.1900 (range: -180 to 180)",
                "min": "-180",
                "max": "180",
                "title": "Longitude must be between -180 and 180",
            }),
        }

    def clean_position(self):
        pos = self.cleaned_data.get("position")
        if pos is None or pos < 1:
            raise forms.ValidationError("Position must be a positive integer (>= 1).")
        return pos

    def clean_latitude(self):
        lat = self.cleaned_data.get("latitude")
        if lat is not None and (lat < -90 or lat > 90):
            raise forms.ValidationError("Latitude must be between -90 and 90.")
        return lat

    def clean_longitude(self):
        lon = self.cleaned_data.get("longitude")
        if lon is not None and (lon < -180 or lon > 180):
            raise forms.ValidationError("Longitude must be between -180 and 180.")
        return lon





class RejectForm(forms.Form):
    message = forms.CharField(
        label="Message (optional)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
