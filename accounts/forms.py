from django import forms
from django.core.exceptions import ValidationError
from core.models import User  # usa il tuo custom User (aggiorna l'import se il path è diverso)
# Se vuoi gestire le lingue ora:
try:
    from core.models import Language
    HAS_LANGUAGE = True
except Exception:
    Language = None
    HAS_LANGUAGE = False


class AccountForm(forms.ModelForm):
    """
    ModelForm per creare/modificare un account.
    - Normalizza email in lowercase.
    - Valida ruolo.
    - (Opzionale) Gestisce lingue se esiste il M2M.
    """
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
        required=False  # obbligatoria solo in create
    )

    class Meta:
        model = User
        fields = ["email", "role", "name", "surname"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
            "role": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "surname": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("Email obbligatoria.")
        # Evitiamo collisioni case-insensitive
        qs = User.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.filter(email__iexact=email).exists():
            raise ValidationError("Esiste già un utente con questa email (case-insensitive).")
        return email

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if role not in dict(User.ROLE_CHOICES):
            raise ValidationError("Ruolo non valido.")
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        # email già normalizzata in clean_email
        pwd = self.cleaned_data.get("password")
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
            # Lingue M2M se presenti
            if HAS_LANGUAGE and hasattr(user, "languages"):
                # il template invia name="lang_ids" (multiplo)
                # le recuperiamo nella view (non qui) per non accedere a self.data in save().
                pass
        return user

# (opzionale) in accounts/forms.py
from django.contrib.auth.forms import AuthenticationForm
from django import forms

class EmailAuthForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("username", "password"):
            self.fields[name].widget.attrs.update({"class": "form-control", "autocomplete": "on"})
