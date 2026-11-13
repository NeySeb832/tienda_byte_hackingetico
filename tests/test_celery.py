"""Celery configuration and smoke task (ADR-0009)."""

from apps.core.tasks import ping
from config.celery import app


def test_ping_task_runs():
    assert ping.delay().get(timeout=5) == "pong"


def test_celery_only_accepts_json():
    assert app.conf.accept_content == ["json"]
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"


def test_celery_is_reliable_by_default():
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_time_limit
