"""Test settings."""

from .base import *  # noqa: F403
from .base import ROOT_DIR


SECRET_KEY = "test-secret-key-with-at-least-32-bytes"
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Use in-memory broker so .delay() calls never try to connect to Redis/RabbitMQ.
# Celery 5 removed task_always_eager; the memory:// transport keeps tests from failing
# with a connection error. Tests that verify task side-effects should mock .delay directly.
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
OTP_EXPOSE_DEBUG_CODES = True

# Use in-memory cache so tests never require a running Redis instance.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/hour",
    "user": "10000/hour",
    "auth_register": "10000/hour",
    "auth_login": "10000/hour",
    "auth_otp": "10000/hour",
    "auth_password_reset": "10000/hour",
}

# Silence all loggers during tests to keep output clean.
LOGGING = {"version": 1, "disable_existing_loggers": True}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ROOT_DIR / "test.sqlite3",
    }
}
