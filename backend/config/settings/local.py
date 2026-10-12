"""Local development settings."""

from .base import *  # noqa: F403


DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "192.168.1.179"]
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Run Celery tasks synchronously in dev — no worker needed.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Allow the Vite dev server to reach the API without a proxy.
# These origins are safe to hardcode here because this file is only ever
# loaded in a local development context.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]



# ── Redis fallback for local development ─────────────────────────────────────
# Live WebSocket pushes need a channel layer and several features need a cache.
# Production settings use Redis for both. On a laptop without Redis running that
# would mean silently dropped live updates, so fall back to in-process backends.
# (In-memory layers are single-process only, which is fine for `runserver`.)
def _redis_reachable(url: str, timeout: float = 0.3) -> bool:
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 6379), timeout=timeout):
            return True
    except OSError:
        return False


if not _redis_reachable(REDIS_URL):  # noqa: F405
    import logging

    logging.getLogger("nhwz.settings").warning(
        "Redis not reachable at %s: using in-memory channel layer and cache (dev only).", REDIS_URL  # noqa: F405
    )
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
