"""Load the Celery app at startup so ``@shared_task`` uses our settings."""

try:
    from .celery import app as celery_app
except ImportError:  # pragma: no cover - Celery not installed in lean envs.
    celery_app = None

__all__ = ("celery_app",)
