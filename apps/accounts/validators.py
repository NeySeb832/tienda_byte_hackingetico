"""Password validators (OWASP A07)."""

import hashlib
import logging
from typing import Any

import httpx
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"


class StaffMinimumLengthValidator:
    """Staff accounts need longer passwords than customers."""

    def __init__(self, min_length: int = 12) -> None:
        self.min_length = min_length

    def validate(self, password: str, user: Any = None) -> None:
        if getattr(user, "is_staff", False) and len(password) < self.min_length:
            raise ValidationError(
                "Las cuentas del personal requieren contraseñas de al menos %(min)d caracteres.",
                code="password_too_short_staff",
                params={"min": self.min_length},
            )

    def get_help_text(self) -> str:
        return f"Si eres parte del personal, usa al menos {self.min_length} caracteres."


def pwned_count(password: str) -> int:
    """How many times the password appears in known breaches (HIBP, k-anonymity).

    Only the first five hex characters of the SHA-1 digest leave the server, as
    required by the Have I Been Pwned range API. If the API is unreachable the
    check is skipped and logged (fail open): the other validators still apply.
    """
    # The HIBP protocol mandates SHA-1; it is not used to protect any data here.
    digest = (
        hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
    )  # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
    prefix, suffix = digest[:5], digest[5:]
    try:
        response = httpx.get(
            HIBP_RANGE_URL.format(prefix=prefix),
            headers={"Add-Padding": "true", "User-Agent": "byte-password-check"},
            timeout=3.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Breached-password check unavailable; skipped")
        return 0
    for line in response.text.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip() == suffix:
            return int(count.strip() or 0)
    return 0


class PwnedPasswordValidator:
    def validate(self, password: str, user: Any = None) -> None:
        if settings.BYTE_HIBP_ENABLED and pwned_count(password) > 0:
            raise ValidationError(
                "Esta contraseña aparece en filtraciones de datos conocidas. Elige otra.",
                code="password_pwned",
            )

    def get_help_text(self) -> str:
        return "No uses contraseñas que hayan aparecido en filtraciones conocidas."
