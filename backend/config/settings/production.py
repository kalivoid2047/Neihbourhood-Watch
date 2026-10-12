"""Production settings."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env, env_bool


SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)

# Belt-and-suspenders: the env() call above already raises if the variable is
# absent, but this catches the case where the variable IS set to the
# development placeholder (e.g. copied from .env.example without changing it).
if SECRET_KEY == "local-development-secret-key":  # noqa: F821
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong random value in production. "
        "Generate one with: python -c 'from django.core.management.utils import "
        "get_random_secret_key; print(get_random_secret_key())'"
    )

DEBUG = env_bool("DJANGO_DEBUG", False)

# ── HTTPS enforcement ──────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── Additional security headers ────────────────────────────────────────────────
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# ── Production JSON logging to stdout (Docker/container friendly) ──────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "WARNING")},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "nhwz": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO"), "propagate": False},
    },
}

try:
    from pythonjsonlogger import jsonlogger as _jl
    LOGGING["formatters"]["json"]["()"] = _jl.JsonFormatter
except ImportError:
    pass

