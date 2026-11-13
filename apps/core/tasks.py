"""Celery tasks of the core app."""

from celery import shared_task


@shared_task(name="core.ping")
def ping() -> str:
    """Smoke-test task used to verify the worker is alive."""
    return "pong"
