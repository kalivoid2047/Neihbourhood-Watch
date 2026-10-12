"""Custom middleware for the NHWZ platform."""

import logging
import time

logger = logging.getLogger("nhwz.requests")


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class RequestLoggingMiddleware:
    """Emit a structured log line for every HTTP request.

    Runs last in the middleware stack so that ``request.user`` is always
    populated (authentication middleware runs before it).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - started_at) * 1000)

        user_id = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.pk)

        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "ip": _get_client_ip(request),
            },
        )
        return response
