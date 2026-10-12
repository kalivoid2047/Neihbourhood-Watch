"""Celery application factory.

Celery is part of the production dependency set. The import is optional so the
local Phase 1 test environment remains runnable when Celery has not been
installed yet.
"""

import os


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

try:
    from celery import Celery
    from celery.schedules import crontab
except ImportError:  # pragma: no cover - exercised only in lean local envs.
    app = None
else:
    app = Celery("nhwz")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()

    app.conf.beat_schedule = {
        "cleanup-expired-otp-challenges": {
            "task": "apps.accounts.tasks.cleanup_expired_otp_challenges",
            "schedule": crontab(hour=2, minute=0),
        },
        "retry-failed-notifications": {
            "task": "apps.notifications.tasks.retry_failed_notifications",
            "schedule": crontab(minute=0),
        },
        "cleanup-old-notifications": {
            "task": "apps.notifications.tasks.cleanup_old_notifications",
            "schedule": crontab(hour=3, minute=0),
        },
        "generate-daily-analytics": {
            "task": "apps.analytics.tasks.generate_daily_snapshots",
            "schedule": crontab(hour=1, minute=0),
        },
    }

