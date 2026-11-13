"""Template context shared by every page: size of the visitor's comparison list."""

from typing import Any

from django.http import HttpRequest

from apps.catalog.services import compare_ids


def catalog(request: HttpRequest) -> dict[str, Any]:
    session = getattr(request, "session", None)
    return {"compare_count": len(compare_ids(session)) if session is not None else 0}
