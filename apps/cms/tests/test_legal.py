"""Versioned legal documents."""

import pytest
from django.urls import reverse

from apps.cms.models import LegalDocument

pytestmark = pytest.mark.django_db


def test_privacy_policy_page_shows_current_version(client):
    response = client.get(reverse("cms:privacy"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Ley 1581 de 2012" in html
    assert "Versión 1.0" in html


def test_missing_document_is_404(client):
    LegalDocument.objects.filter(kind=LegalDocument.Kind.TERMS).delete()
    assert client.get(reverse("cms:terms")).status_code == 404
