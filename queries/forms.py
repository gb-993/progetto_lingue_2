from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import Language, ParameterDef

# -----------------------
# Helper widget uniformi
# -----------------------
_SELECT = {"class": "form-select"}
_INPUT = {"class": "form-control"}

class ParamPickForm(forms.Form):
    parameter = forms.ModelChoiceField(
        queryset=ParameterDef.objects.order_by("position"),
        required=True,
        label=_("Parameter"),
        widget=forms.Select(attrs=_SELECT),
    )

class ParamNeutralizationForm(forms.Form):
    language = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Language"),
        widget=forms.Select(attrs=_SELECT),
    )
    parameter = forms.ModelChoiceField(
        queryset=ParameterDef.objects.order_by("position"),
        required=True,
        label=_("Parameter"),
        widget=forms.Select(attrs=_SELECT),
    )

class LangOnlyForm(forms.Form):
    language = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Language"),
        widget=forms.Select(attrs=_SELECT),
    )

class LangPairForm(forms.Form):
    language_a = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("First language"),
        widget=forms.Select(attrs=_SELECT),
    )
    language_b = forms.ModelChoiceField(
        queryset=Language.objects.order_by("position"),
        required=True,
        label=_("Second language"),
        widget=forms.Select(attrs=_SELECT),
    )

    def clean(self):
        data = super().clean()
        a = data.get("language_a")
        b = data.get("language_b")
        if a and b and a.pk == b.pk:
            self.add_error("language_b", _("Select two different languages"))
        return data
