"""Customer addresses: CRUD, single default address and IDOR protection (A01)."""

import uuid

import pytest
from django.urls import reverse

from apps.accounts.models import Address
from apps.accounts.services import MAX_ADDRESSES
from apps.core.models import City

pytestmark = pytest.mark.django_db


def address_data(**overrides):
    data = {
        "label": "Casa",
        "recipient_name": "Ana Pérez",
        "phone": "300 123 4567",
        "city": City.objects.get(code="05001").pk,
        "line1": "Carrera 43A # 1-50",
        "line2": "Apto 501",
        "neighborhood": "El Poblado",
        "notes": "",
    }
    data.update(overrides)
    return data


def test_customer_creates_address_and_first_one_is_default(client, customer):
    client.force_login(customer)
    response = client.post(reverse("accounts:address_create"), address_data())
    assert response.status_code == 302
    address = Address.objects.get(user=customer)
    assert address.is_default is True
    assert address.phone == "3001234567"


def test_only_one_default_address(client, customer):
    client.force_login(customer)
    client.post(reverse("accounts:address_create"), address_data(label="Casa"))
    client.post(reverse("accounts:address_create"), address_data(label="Oficina", is_default="on"))
    defaults = Address.objects.filter(user=customer, is_default=True)
    assert list(defaults.values_list("label", flat=True)) == ["Oficina"]


def test_invalid_phone_is_rejected(client, customer):
    client.force_login(customer)
    response = client.post(reverse("accounts:address_create"), address_data(phone="12345"))
    assert response.status_code == 200
    assert not Address.objects.filter(user=customer).exists()


def test_address_limit(client, customer):
    client.force_login(customer)
    for n in range(MAX_ADDRESSES):
        client.post(reverse("accounts:address_create"), address_data(label=f"Dir {n}"))
    response = client.post(reverse("accounts:address_create"), address_data(label="Extra"))
    assert response.status_code == 200
    assert Address.objects.filter(user=customer).count() == MAX_ADDRESSES


@pytest.mark.security
@pytest.mark.parametrize("view", ["accounts:address_update", "accounts:address_delete"])
def test_idor_on_another_customers_address(client, customer, role_user, view):
    """Swapping the UUID for someone else's address must look exactly like a missing one."""
    owner = role_user("Cliente")
    client.force_login(owner)
    client.post(reverse("accounts:address_create"), address_data())
    target = Address.objects.get(user=owner)

    client.force_login(customer)
    for method in ("get", "post"):
        response = getattr(client, method)(reverse(view, args=[target.public_id]))
        assert response.status_code == 404
    assert Address.objects.filter(pk=target.pk).exists()
    random_id = client.get(reverse(view, args=[uuid.uuid4()]))
    assert random_id.status_code == 404


def test_delete_default_promotes_another(client, customer):
    client.force_login(customer)
    client.post(reverse("accounts:address_create"), address_data(label="Casa"))
    client.post(reverse("accounts:address_create"), address_data(label="Oficina"))
    default = Address.objects.get(user=customer, is_default=True)
    client.post(reverse("accounts:address_delete", args=[default.public_id]))
    assert Address.objects.get(user=customer).is_default is True
