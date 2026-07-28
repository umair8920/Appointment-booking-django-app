"""Import Celery app so shared_task binds correctly on Django startup."""

from .celery import app as celery_app

__all__ = ("celery_app",)
