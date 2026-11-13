"""Forms for the accounts app. Validation here is authoritative (server side)."""

import re
from typing import Any

from allauth.account.forms import LoginForm as AllauthLoginForm
from allauth.account.forms import ResetPasswordForm as AllauthResetPasswordForm
from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.conf import settings
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.http import HttpRequest

from apps.accounts import roles
from apps.accounts.captcha import TurnstileField
from apps.accounts.models import Address, CustomerProfile, User
from apps.accounts.security import recent_failures
from apps.audit.services import client_ip
from apps.core.models import City

HONEYPOT_FIELD = "website"
PHONE_RE = re.compile(r"^(\+?57)?3\d{9}$")
DOCUMENT_RE = re.compile(r"^[A-Za-z0-9]{5,15}$")


class UserAdminCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "is_active", "is_staff", "is_superuser")


def add_honeypot(form: forms.Form) -> None:
    """Invisible field that people never fill in but naive bots do."""
    form.fields[HONEYPOT_FIELD] = forms.CharField(
        label="Deja este campo vacío",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )


def check_honeypot(form: forms.Form) -> None:
    if form.cleaned_data.get(HONEYPOT_FIELD):
        raise forms.ValidationError("No pudimos procesar la solicitud.", code="honeypot")


def add_captcha(form: forms.Form, request: HttpRequest | None = None) -> None:
    if settings.BYTE_CAPTCHA_ENABLED:
        field = TurnstileField()
        field.remote_ip = client_ip(request)
        form.fields["captcha"] = field


class LoginForm(AllauthLoginForm):
    """Email + password; a CAPTCHA appears after repeated failures from the same IP."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if recent_failures(self.request) >= settings.BYTE_LOGIN_CAPTCHA_AFTER_FAILURES:
            add_captcha(self, self.request)


class SignupForm(AllauthSignupForm):
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    accept_privacy = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales según la política de privacidad",
        required=True,
        error_messages={
            "required": "Debes aceptar la política de tratamiento de datos para registrarte."
        },
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        add_honeypot(self)
        add_captcha(self)
        self.order_fields(
            ["first_name", "last_name", "email", "password1", "password2", "accept_privacy"]
        )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        check_honeypot(self)
        return cleaned

    def save(self, request: HttpRequest) -> User:
        from apps.accounts.services import complete_customer_signup

        user: User = super().save(request)
        complete_customer_signup(user, request=request)
        return user


class ResetPasswordForm(AllauthResetPasswordForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        add_honeypot(self)
        add_captcha(self)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        check_honeypot(self)
        return cleaned


def normalize_phone(value: str) -> str:
    digits = re.sub(r"[\s\-()]", "", value)
    if not PHONE_RE.match(digits):
        raise forms.ValidationError(
            "Ingresa un celular colombiano válido (10 dígitos, empieza por 3)."
        )
    return digits[-10:]


class ProfileForm(forms.Form):
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    document_type = forms.ChoiceField(
        label="Tipo de documento",
        choices=[("", "—"), *CustomerProfile.DocumentType.choices],
        required=False,
    )
    document_number = forms.CharField(label="Número de documento", max_length=15, required=False)
    phone = forms.CharField(label="Celular", max_length=20, required=False)
    marketing_opt_in = forms.BooleanField(
        label="Quiero recibir ofertas y novedades por correo", required=False
    )

    def clean_document_number(self) -> str:
        value = "".join(self.cleaned_data["document_number"].split())
        if value and not DOCUMENT_RE.match(value):
            raise forms.ValidationError("El documento debe tener entre 5 y 15 letras o números.")
        return value

    def clean_phone(self) -> str:
        value = self.cleaned_data["phone"].strip()
        return normalize_phone(value) if value else ""

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if bool(cleaned.get("document_type")) != bool(cleaned.get("document_number")):
            raise forms.ValidationError("Indica el tipo y el número de documento.")
        return cleaned


class CityChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: City) -> str:
        return f"{obj.name} ({obj.department.name})"


class AddressForm(forms.ModelForm):
    city = CityChoiceField(
        label="Ciudad", queryset=City.objects.select_related("department").order_by("name")
    )

    class Meta:
        model = Address
        fields = (
            "label",
            "recipient_name",
            "phone",
            "city",
            "line1",
            "line2",
            "neighborhood",
            "notes",
            "is_default",
        )
        widgets = {"phone": forms.TextInput(attrs={"inputmode": "tel"})}

    def clean_phone(self) -> str:
        return normalize_phone(self.cleaned_data["phone"])


class RoleAssignmentForm(forms.Form):
    email = forms.EmailField(label="Correo del usuario")
    role = forms.ChoiceField(label="Rol", choices=())

    def __init__(self, *args: Any, actor: User, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        allowed = roles.ALL_ROLES if actor.is_superuser else roles.ASSIGNABLE_BY_ADMIN
        role_field = self.fields["role"]
        assert isinstance(role_field, forms.ChoiceField)  # noqa: S101 - typing narrow
        role_field.choices = [(role, role) for role in allowed]


class AccountDeletionForm(forms.Form):
    password = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    confirmation = forms.CharField(label="Escribe ELIMINAR para confirmar", max_length=20)

    def __init__(self, *args: Any, user: User, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self) -> str:
        password: str = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("La contraseña no es correcta.")
        return password

    def clean_confirmation(self) -> str:
        value: str = self.cleaned_data["confirmation"].strip()
        if value != "ELIMINAR":
            raise forms.ValidationError("Escribe ELIMINAR en mayúsculas para confirmar.")
        return value
