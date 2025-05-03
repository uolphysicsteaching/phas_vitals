"""Main phas_vitals project package with global settings and config."""

# app imports
from .tasks import tasks as celery_app

__all__ = ("celery_app",)
