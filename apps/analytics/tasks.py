"""Nightly BI pipeline (Celery Beat)."""

from typing import Any

from celery import shared_task

from apps.analytics import pipeline


@shared_task(name="analytics.run_pipeline")
def run_pipeline() -> dict[str, Any]:
    return pipeline.run()
