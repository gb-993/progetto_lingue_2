from django import forms
from core.models import Glossary
from django.core.exceptions import ValidationError

class GlossaryForm(forms.ModelForm):
    class Meta:
        model = Glossary
        fields = ["word", "description"]
        widgets = {
            "word": forms.TextInput(attrs={
                "class": "form-control",
                "autocomplete": "off",
                "aria-describedby": "word-help",
                "inputmode": "text"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6,
                "aria-describedby": "desc-help"
            }),
        }

    def clean_word(self):
        w = (self.cleaned_data.get("word") or "").strip()
        if not w:
            raise ValidationError("This entry is mandatory.")
        qs = Glossary.objects.filter(word__iexact=w)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("An entry with this word already exists.")
        return w
