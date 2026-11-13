"""Health checks used by /healthz (platform health check)."""

import logging
import uuid
from dataclasses import dataclass

from django.core.cache import cache
from django.db import connections

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HealthReport:
    checks: dict[str, bool]

    @property
    def healthy(self) -> bool:
        return all(self.checks.values())


def check_database() -> bool:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check failed: database")
        return False
    return True


def check_cache() -> bool:
    probe = uuid.uuid4().hex
    try:
        cache.set("healthz:probe", probe, timeout=10)
        return bool(cache.get("healthz:probe") == probe)
    except Exception:
        logger.exception("Health check failed: cache")
        return False


def run_health_checks() -> HealthReport:
    return HealthReport(checks={"database": check_database(), "cache": check_cache()})
