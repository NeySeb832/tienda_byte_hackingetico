"""Read-side queries for the accounts app.

Selectors return querysets already scoped to what the requesting user may see
(deny by default) and use select_related/prefetch_related to avoid N+1 queries.
"""

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from apps.accounts.models import Address, ConsentRecord, User
from apps.inventory.models import Store


def addresses_for(user: User) -> QuerySet[Address]:
    return Address.objects.filter(user=user).select_related("city__department")


def address_for(user: User, public_id: object) -> Address:
    """An address of ``user``; anything else is a 404 (no IDOR, no existence leak)."""
    return get_object_or_404(addresses_for(user), public_id=public_id)


def consents_for(user: User) -> QuerySet[ConsentRecord]:
    return ConsentRecord.objects.filter(user=user).select_related("document")


def staff_members() -> QuerySet[User]:
    return User.objects.filter(is_staff=True).prefetch_related("groups").order_by("email")


def stores_for(user: User) -> QuerySet[Store]:
    """Stores within the user's scope: all for admins, assigned ones for everyone else."""
    if user.is_superuser or user.has_perm("accounts.manage_staff"):
        return Store.objects.all()
    return Store.objects.filter(staff_assignments__user=user)
