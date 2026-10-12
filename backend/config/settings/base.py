"""Base settings for the NHWZ backend."""

from datetime import timedelta
import importlib.util
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from django.core.exceptions import ImproperlyConfigured


ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = ROOT_DIR / "backend"


def env(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.getenv(name, default)
    if required and value in (None, ""):
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


SECRET_KEY = env("DJANGO_SECRET_KEY", "local-development-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "apps.core",
    "apps.accounts",
    "apps.neighborhoods",
    "apps.incidents",
    "apps.notifications",
    "apps.sos",
    "apps.audit",
    "apps.sync",
    "apps.analytics",
]

if module_available("axes"):
    INSTALLED_APPS.append("axes")

if module_available("drf_spectacular"):
    INSTALLED_APPS.append("drf_spectacular")

if module_available("channels"):
    INSTALLED_APPS.append("channels")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestLoggingMiddleware",
]

if module_available("axes"):
    MIDDLEWARE.append("axes.middleware.AxesMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BACKEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def database_from_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    engine = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "postgis": "django.contrib.gis.db.backends.postgis",
    }.get(scheme)
    if engine is None:
        raise ImproperlyConfigured(f"Unsupported DATABASE_URL scheme: {scheme}")

    config: dict[str, object] = {
        "ENGINE": engine,
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }
    options = dict(parse_qsl(parsed.query))
    if options:
        config["OPTIONS"] = options
    return config


database_url = env("DATABASE_URL")
if database_url:
    DATABASES = {"default": database_from_url(database_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ROOT_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Harare"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = ROOT_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
        "user": "2000/hour",
        "auth_register": "20/hour",
        "auth_login": "20/hour",
        "auth_otp": "10/hour",
        "auth_password_reset": "10/hour",
    },
}

if module_available("drf_spectacular"):
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
# Lax is safe for JWT-based APIs: cookies are only sent on same-site navigations.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)

USE_S3_STORAGE = env_bool("USE_S3_STORAGE", False)

if USE_S3_STORAGE:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "endpoint_url": env("MINIO_ENDPOINT_URL"),
                "access_key": env("MINIO_ACCESS_KEY"),
                "secret_key": env("MINIO_SECRET_KEY"),
                "bucket_name": env("MINIO_BUCKET_NAME", "nhwz-media"),
                "file_overwrite": False,
                "default_acl": "private",
                "querystring_auth": True,
                "querystring_expire": 3600,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

MINIO_ENDPOINT_URL = env("MINIO_ENDPOINT_URL")
MINIO_ACCESS_KEY = env("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = env("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = env("MINIO_BUCKET_NAME", "nhwz-media")

EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@nhwz.example.com")

OTP_LENGTH = env_int("OTP_LENGTH", 6)
OTP_TTL_MINUTES = env_int("OTP_TTL_MINUTES", 10)
OTP_MAX_ATTEMPTS = env_int("OTP_MAX_ATTEMPTS", 5)
OTP_EXPOSE_DEBUG_CODES = env_bool("OTP_EXPOSE_DEBUG_CODES", DEBUG)

# ── Notification rate limiting ─────────────────────────────────────────────────
# Maximum number of notifications a user may receive per channel within the window.
NOTIFICATION_RATE_LIMIT_MAX = env_int("NOTIFICATION_RATE_LIMIT_MAX", 20)
NOTIFICATION_RATE_LIMIT_WINDOW_MINUTES = env_int("NOTIFICATION_RATE_LIMIT_WINDOW_MINUTES", 60)

# ── Push notifications (Firebase Cloud Messaging) ─────────────────────────────
# Used by apps.notifications.fcm to wake the mobile app's alarm engine.
# Without these the app still alarms, but only on its own polling schedule —
# up to 15 minutes late when it is running in the background.
# See docs/FIREBASE_SETUP.md for how to obtain them.
FCM_ENABLED = env_bool("FCM_ENABLED", True)
FCM_PROJECT_ID = env("FCM_PROJECT_ID", "")
FCM_CREDENTIALS_FILE = env("FCM_CREDENTIALS_FILE", "")

# ── Incident alerting ──────────────────────────────────────────────────────────
# Fallback radius, in metres, when an incident has no neighbourhood (and so no
# Neighborhood.alert_radius_m to read).
INCIDENT_ALERT_DEFAULT_RADIUS_M = env_int("INCIDENT_ALERT_DEFAULT_RADIUS_M", 5000)

# Anyone whose device is within this many metres of an incident can see it on
# their map and open it, even if they have not joined its neighbourhood.
INCIDENT_NEARBY_VISIBILITY_RADIUS_M = env_int("INCIDENT_NEARBY_VISIBILITY_RADIUS_M", 5000)

# Users within this many metres of a new SOS alert (or in the sender's
# neighbourhood) get a siren.  Smaller than the incident radius: an SOS is
# something a neighbour could actually walk to.
SOS_ALERT_RADIUS_M = env_int("SOS_ALERT_RADIUS_M", 2000)

# Severities that alert neighbours the moment they are reported, before a
# coordinator has verified them. Everything else waits for verification.
# This is a community-policy trade-off: faster warnings versus fewer false
# alarms. Set to an empty list to require verification for everything.
INCIDENT_ALERT_ON_CREATE_SEVERITIES = [
    value.strip()
    for value in env("INCIDENT_ALERT_ON_CREATE_SEVERITIES", "red").split(",")
    if value.strip()
]

# ── Application version ────────────────────────────────────────────────────────
APP_VERSION = env("APP_VERSION", "7.0.0")

# ── Security headers (safe to enable in all environments) ─────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Structured logging ─────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", "WARNING"),
    },
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "nhwz": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO"), "propagate": False},
    },
}

if module_available("pythonjsonlogger"):
    from pythonjsonlogger import jsonlogger as _jl  # noqa: E402
    LOGGING["formatters"]["json"] = {
        "()": _jl.JsonFormatter,
        "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
    }
    LOGGING["handlers"]["console"]["formatter"] = "json"

# ── Sentry error tracking ──────────────────────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", "")
if SENTRY_DSN and module_available("sentry_sdk"):
    import sentry_sdk  # noqa: E402
    from sentry_sdk.integrations.celery import CeleryIntegration  # noqa: E402
    from sentry_sdk.integrations.django import DjangoIntegration  # noqa: E402

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
        environment=env("DJANGO_ENV", "local"),
        release=APP_VERSION,
        send_default_pii=False,
    )
