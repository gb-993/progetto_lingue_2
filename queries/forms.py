from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import Language, ParameterDef

# -----------------------
# Helper widget uniformi
# -----------------------
_SELECT = {"class": "form-select"}
_INPUT = {"class": "form-control"}

class ParamPickForm(forms.Form):
    """Per-query #1 e #2: selezione parametro."""
    parameter = forms.ModelChoiceField(
        queryset=ParameterDef.objects.order_by("position"),
        required=True,
        label=_("Parametro"),
        widget=forms.Select(attrs=_SELECT),
    )

class ParamNeutralizationForm(forms.Form):
    """Per-query #3: param & lingua per vedere perché è stato neutralizzato (0)."""
    language = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Lingua"),
        widget=forms.Select(attrs=_SELECT),
    )
    parameter = forms.ModelChoiceField(
        queryset=ParameterDef.objects.order_by("position"),
        required=True,
        label=_("Parametro"),
        widget=forms.Select(attrs=_SELECT),
    )

class LangOnlyForm(forms.Form):
    """Per-query #4, #5, #6: selezione lingua."""
    language = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Lingua"),
        widget=forms.Select(attrs=_SELECT),
    )

class LangPairForm(forms.Form):
    """Per-query #7: coppia di lingue per la mini-Table A."""
    language_a = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Lingua A"),
        widget=forms.Select(attrs=_SELECT),
    )
    language_b = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Lingua B"),
        widget=forms.Select(attrs=_SELECT),
    )

    def clean(self):
        data = super().clean()
        a = data.get("language_a")
        b = data.get("language_b")
        if a and b and a.pk == b.pk:
            self.add_error("language_b", _("Scegli due lingue diverse"))
        return data
