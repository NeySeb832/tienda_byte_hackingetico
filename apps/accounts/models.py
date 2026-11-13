"""Users of Byte (customers and staff). Email is the login identifier (ADR-0011)."""

from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.crypto import EncryptedTextField, blind_index
from apps.core.models import BaseModel, PublicIdModel, TimeStampedModel


def normalize_email_address(email: str) -> str:
    """Emails are stored trimmed and lower-cased (one account per mailbox)."""
    return email.strip().lower()


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=normalize_email_address(email), **extra_fields)
        user.set_password(password)  # None -> unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username: str | None) -> "User":
        return self.get(**{self.model.USERNAME_FIELD: normalize_email_address(username or "")})


class User(PublicIdModel, AbstractUser):
    username = None  # type: ignore[assignment]  # email is the login identifier
    email = models.EmailField(_("correo electrónico"), unique=True)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = _("usuario")
        verbose_name_plural = _("usuarios")
        permissions = [
            ("access_panel", "Puede acceder al panel"),
            ("manage_staff", "Puede gestionar el personal y sus roles"),
            ("view_customers", "Puede consultar clientes (CRM)"),
        ]
        constraints = [
            # Defence in depth: even raw updates cannot store a mixed-case email.
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")), name="accounts_user_email_lowercase"
            ),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = normalize_email_address(self.email)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.email:
            self.email = normalize_email_address(self.email)
        super().save(*args, **kwargs)


class CustomerProfile(TimeStampedModel):
    """Personal data of a customer. Document and phone are encrypted at rest (A04)."""

    class DocumentType(models.TextChoices):
        CC = "CC", _("Cédula de ciudadanía")
        CE = "CE", _("Cédula de extranjería")
        NIT = "NIT", _("NIT")
        PA = "PA", _("Pasaporte")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    document_type = models.CharField(
        _("tipo de documento"), max_length=3, choices=DocumentType.choices, blank=True
    )
    document_number = EncryptedTextField(_("número de documento"), blank=True)
    document_index = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
    phone = EncryptedTextField(_("celular"), blank=True)
    marketing_opt_in = models.BooleanField(_("acepta comunicaciones comerciales"), default=False)

    class Meta:
        verbose_name = _("perfil de cliente")
        verbose_name_plural = _("perfiles de cliente")

    def __str__(self) -> str:
        return f"Perfil de {self.user}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.document_index = (
            blind_index(f"{self.document_type}:{self.document_number}")
            if self.document_number
            else ""
        )
        super().save(*args, **kwargs)


class Address(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(_("nombre de la dirección"), max_length=60)
    recipient_name = models.CharField(_("quién recibe"), max_length=120)
    phone = EncryptedTextField(_("celular de contacto"))
    city = models.ForeignKey("core.City", on_delete=models.PROTECT, verbose_name=_("ciudad"))
    line1 = models.CharField(_("dirección"), max_length=200)
    line2 = models.CharField(_("complemento"), max_length=200, blank=True)
    neighborhood = models.CharField(_("barrio"), max_length=120, blank=True)
    notes = models.CharField(_("indicaciones para la entrega"), max_length=255, blank=True)
    is_default = models.BooleanField(_("predeterminada"), default=False)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = _("dirección")
        verbose_name_plural = _("direcciones")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="accounts_address_one_default_per_user",
            )
        ]

    def __str__(self) -> str:
        return self.label


class ConsentRecord(models.Model):
    """Proof of the data-processing authorisation (Ley 1581 de 2012, Decreto 1377 de 2013)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consents")
    document = models.ForeignKey("cms.LegalDocument", on_delete=models.PROTECT, related_name="+")
    accepted_at = models.DateTimeField(_("aceptado"), default=timezone.now)
    ip = models.GenericIPAddressField(_("IP"), null=True, blank=True)
    user_agent = models.CharField(_("navegador"), max_length=255, blank=True)
    revoked_at = models.DateTimeField(_("revocado"), null=True, blank=True)

    class Meta:
        ordering = ["-accepted_at"]
        verbose_name = _("autorización de datos")
        verbose_name_plural = _("autorizaciones de datos")

    def __str__(self) -> str:
        return f"{self.document} ({self.accepted_at:%Y-%m-%d})"


class StaffStoreAssignment(models.Model):
    """Stores a staff member works at; scopes what managers and staff can see."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="store_assignments")
    store = models.ForeignKey(
        "inventory.Store", on_delete=models.CASCADE, related_name="staff_assignments"
    )
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("asignación de sede")
        verbose_name_plural = _("asignaciones de sede")
        constraints = [
            models.UniqueConstraint(fields=["user", "store"], name="accounts_staff_store_unique")
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.store}"
