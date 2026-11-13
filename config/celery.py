"""Celery application. Configuration lives in Django settings (CELERY_* keys)."""

import os
from logging.config import dictConfig
from typing import Any

from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("byte")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@setup_logging.connect
def use_django_logging(**kwargs: Any) -> None:
    """Keep Django's LOGGING (JSON, correlation id, masking) in workers (OWASP A09).

    Without this receiver Celery replaces the logging configuration and task
    execution events were silently dropped.
    """
    from django.conf import settings

    dictConfig(settings.LOGGING)
