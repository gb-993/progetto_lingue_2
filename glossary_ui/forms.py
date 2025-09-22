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
        # normalizziamo: niente spazi doppi, case-fold per evitare duplicati per maiuscole/minuscole
        w = (self.cleaned_data.get("word") or "").strip()
        if not w:
            raise ValidationError("La parola è obbligatoria.")
        # Evita duplicati case-insensitive diversi dalla stessa istanza
        qs = Glossary.objects.filter(word__iexact=w)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Esiste già una voce (ignora maiuscole/minuscole) con questa parola.")
        return w
