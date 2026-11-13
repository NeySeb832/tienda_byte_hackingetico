"""Business logic (write side) for the accounts app.

Services are the only place allowed to change domain state: they validate
business rules, run inside transactions and record audit events.
"""

from typing import Any

from allauth.account.models import EmailAddress
from allauth.usersessions.models import UserSession
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.models import Address, ConsentRecord, CustomerProfile, User
from apps.audit.models import SecurityEvent
from apps.audit.services import client_ip, record_event, record_security_event
from apps.cms.models import LegalDocument
from apps.cms.selectors import current_legal_document

MAX_ADDRESSES = 10


def record_consent(user: User, *, request: HttpRequest | None = None) -> ConsentRecord:
    document = current_legal_document(LegalDocument.Kind.PRIVACY)
    if document is None:
        raise ValidationError("No hay una política de tratamiento de datos publicada.")
    consent = ConsentRecord.objects.create(
        user=user,
        document=document,
        ip=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
    )
    record_event(
        "accounts.consent_granted",
        actor=user,
        target=user,
        changes={"document": str(document)},
        request=request,
    )
    return consent


@transaction.atomic
def complete_customer_signup(user: User, *, request: HttpRequest | None = None) -> None:
    """Profile, customer role and proof of consent for a new account."""
    CustomerProfile.objects.get_or_create(user=user)
    customer, _ = Group.objects.get_or_create(name=roles.CUSTOMER)
    user.groups.add(customer)
    record_event("accounts.signup", actor=user, target=user, request=request)
    record_consent(user, request=request)


@transaction.atomic
def update_profile(
    user: User, data: dict[str, Any], *, request: HttpRequest | None = None
) -> CustomerProfile:
    profile, _ = CustomerProfile.objects.select_for_update().get_or_create(user=user)
    user.first_name = data["first_name"]
    user.last_name = data["last_name"]
    user.save(update_fields=["first_name", "last_name"])
    changed = []
    for field in ("document_type", "document_number", "phone", "marketing_opt_in"):
        if getattr(profile, field) != data.get(field, getattr(profile, field)):
            changed.append(field)
            setattr(profile, field, data[field])
    profile.save()
    record_event(
        "accounts.profile_updated",
        actor=user,
        target=user,
        changes={"fields": changed},
        request=request,
    )
    return profile


@transaction.atomic
def save_address(
    user: User,
    address: Address,
    *,
    request: HttpRequest | None = None,
) -> Address:
    """Create or update an address of ``user``; keeps exactly one default address."""
    if address.user_id is not None and address.user_id != user.pk:
        raise PermissionDenied
    others = Address.objects.select_for_update().filter(user=user)
    if address._state.adding:
        if others.count() >= MAX_ADDRESSES:
            raise ValidationError(f"Puedes guardar hasta {MAX_ADDRESSES} direcciones.")
        address.user = user
        if not others.exists():
            address.is_default = True
    if address.is_default:
        others.exclude(pk=address.pk).filter(is_default=True).update(is_default=False)
    address.save()
    record_event("accounts.address_saved", actor=user, target=address, request=request)
    return address


@transaction.atomic
def delete_address(user: User, address: Address, *, request: HttpRequest | None = None) -> None:
    if address.user_id != user.pk:
        raise PermissionDenied
    was_default = address.is_default
    record_event("accounts.address_deleted", actor=user, target=address, request=request)
    address.delete()
    if was_default:
        replacement = Address.objects.filter(user=user).order_by("-created_at").first()
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=["is_default", "updated_at"])


def role_of(user: User) -> str | None:
    names = set(user.groups.values_list("name", flat=True))
    for role in reversed(roles.ALL_ROLES):  # most privileged first
        if role in names:
            return role
    return None


def end_user_sessions(user: User) -> int:
    """Close every session of ``user`` (forces a new login with the new privileges)."""
    sessions = UserSession.objects.purge_and_list(user)
    for session in sessions:
        session.end()
    return len(sessions)


@transaction.atomic
def assign_role(*, actor: User, user: User, role: str, request: HttpRequest | None = None) -> None:
    """Change the role of ``user``. Separation of duties and least privilege apply."""
    if role not in roles.ALL_ROLES:
        raise ValidationError("Rol desconocido.")
    if not actor.has_perm("accounts.manage_staff"):
        raise PermissionDenied
    if actor.pk == user.pk:
        raise PermissionDenied("No puedes cambiar tu propio rol.")
    if (role == roles.SUPERADMIN or user.is_superuser) and not actor.is_superuser:
        raise PermissionDenied("Solo un superadmin puede gestionar superadmins.")

    previous = role_of(user)
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.set([group])
    user.is_staff = role in roles.STAFF_ROLES
    user.is_superuser = role == roles.SUPERADMIN
    user.save(update_fields=["is_staff", "is_superuser"])
    record_event(
        "accounts.role_changed",
        actor=actor,
        target=user,
        changes={"before": previous, "after": role},
        request=request,
    )
    if role in roles.PRIVILEGED_ROLES:
        record_security_event(
            SecurityEvent.Kind.ROLE_ESCALATION,
            SecurityEvent.Severity.HIGH,
            user=user,
            request=request,
            details={"role": role, "by": actor.pk},
        )
    transaction.on_commit(lambda: end_user_sessions(user))


def export_personal_data(user: User) -> dict[str, Any]:
    """Everything Byte stores about ``user`` (right of access, Ley 1581)."""
    profile = CustomerProfile.objects.filter(user=user).first()
    return {
        "cuenta": {
            "correo": user.email,
            "nombres": user.first_name,
            "apellidos": user.last_name,
            "fecha_registro": user.date_joined.isoformat(),
        },
        "perfil": {
            "tipo_documento": profile.document_type if profile else "",
            "numero_documento": profile.document_number if profile else "",
            "celular": profile.phone if profile else "",
            "acepta_comunicaciones": profile.marketing_opt_in if profile else False,
        },
        "direcciones": [
            {
                "nombre": a.label,
                "recibe": a.recipient_name,
                "celular": a.phone,
                "ciudad": a.city.name,
                "departamento": a.city.department.name,
                "direccion": a.line1,
                "complemento": a.line2,
                "barrio": a.neighborhood,
            }
            for a in Address.objects.filter(user=user).select_related("city__department")
        ],
        "autorizaciones": [
            {
                "documento": str(c.document),
                "aceptada": c.accepted_at.isoformat(),
                "revocada": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in ConsentRecord.objects.filter(user=user).select_related("document")
        ],
    }


@transaction.atomic
def delete_account(user: User, *, request: HttpRequest | None = None) -> None:
    """Right of erasure: anonymise the account, keep only what the law requires."""
    record_event("accounts.account_deleted", actor=user, target=user, request=request)
    Address.objects.filter(user=user).delete()
    CustomerProfile.objects.filter(user=user).delete()
    ConsentRecord.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    user.email = f"eliminado-{user.public_id}@usuarios.invalid"
    user.first_name = ""
    user.last_name = ""
    user.is_active = False
    user.set_unusable_password()
    user.save()
    EmailAddress.objects.filter(user=user).delete()
    end_user_sessions(user)
