"""Firebase Cloud Messaging HTTP v1 client.

Kept deliberately small and dependency-light: a service-account JSON key, an
OAuth2 access token, and one POST per device token.

Configuration (settings or environment):
    FCM_PROJECT_ID            Firebase project id, e.g. "neighbourhood-watch-za"
    FCM_CREDENTIALS_FILE      Path to the service-account JSON key
    FCM_ENABLED               Set False to no-op (tests, local development)

If the credentials are absent the client reports itself unavailable and the
caller falls back gracefully, because the mobile app also polls — a missing
push key degrades alarm latency, it does not break alarms.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)

# FCM returns these when a token is dead — the device was wiped, the app was
# uninstalled, or the token was reissued. Either way, stop using it.
DEAD_TOKEN_ERRORS = {"UNREGISTERED", "INVALID_ARGUMENT", "NOT_FOUND", "SENDER_ID_MISMATCH"}

_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FCMUnavailable(RuntimeError):
    """Raised when FCM is not configured; callers should degrade, not crash."""


class FCMClient:
    """Sends data-only messages through the FCM HTTP v1 API.

    Messages are **data-only** on purpose. A `notification` block would be
    rendered by the OS before our code sees it, which would bypass the client's
    alarm rules (radius, severity threshold, quiet hours) and turn every push
    into the same generic ping.
    """

    _lock = threading.Lock()
    _credentials = None

    def __init__(self):
        self.project_id = getattr(settings, "FCM_PROJECT_ID", "") or ""
        self.credentials_file = getattr(settings, "FCM_CREDENTIALS_FILE", "") or ""
        self.enabled = getattr(settings, "FCM_ENABLED", True)

    @property
    def endpoint(self) -> str:
        return f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"

    def is_available(self) -> bool:
        """Whether a send could actually succeed right now."""
        if not self.enabled or not self.project_id or not self.credentials_file:
            return False
        try:
            import google.oauth2.service_account  # noqa: F401
            import requests  # noqa: F401
        except ImportError:
            return False
        return True

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _access_token(self) -> str:
        """Returns a cached OAuth2 access token, refreshing it when stale.

        The credentials object is shared across threads and refreshes itself,
        so the lock only guards the one-time construction.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover - import guard
            raise FCMUnavailable("google-auth is not installed") from exc

        with self._lock:
            if FCMClient._credentials is None:
                FCMClient._credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file, scopes=[_SCOPE]
                )

        credentials = FCMClient._credentials
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token

    # ── Sending ───────────────────────────────────────────────────────────────

    def send(self, *, token: str, data: dict[str, Any], priority_high: bool = True) -> tuple[bool, str]:
        """Sends one data message.

        Returns ``(delivered, detail)``. ``detail`` carries the FCM error status
        when delivery failed, so the caller can prune dead tokens.
        """
        if not self.is_available():
            raise FCMUnavailable("FCM is not configured")

        import requests

        # Every value in an FCM data payload must be a string.
        payload = {
            "message": {
                "token": token,
                "data": {key: str(value) for key, value in data.items() if value is not None},
                "android": {
                    # "high" is what lets a data message wake a dozing device;
                    # a normal-priority message may be held until the next
                    # maintenance window, which is useless for a safety alarm.
                    "priority": "high" if priority_high else "normal",
                },
                "apns": {
                    "headers": {
                        "apns-priority": "10" if priority_high else "5",
                        # Required for a data-only push to be delivered
                        # promptly on iOS.
                        "apns-push-type": "background" if not priority_high else "alert",
                    },
                    "payload": {"aps": {"content-available": 1}},
                },
            }
        }

        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self._access_token()}",
                    "Content-Type": "application/json; UTF-8",
                },
                data=json.dumps(payload),
                timeout=10,
            )
        except Exception as exc:  # network error, DNS, TLS
            logger.warning("FCM request failed: %s", exc)
            return False, f"transport error: {exc}"

        if response.status_code == 200:
            return True, "ok"

        status = _error_status(response)
        logger.warning("FCM rejected a message (%s): %s", response.status_code, status)
        return False, status


def _error_status(response) -> str:
    """Extracts FCM's machine-readable error status from a failure response."""
    try:
        body = response.json()
    except ValueError:
        return f"http {response.status_code}"

    error = body.get("error", {})
    for detail in error.get("details", []):
        if "errorCode" in detail:
            return detail["errorCode"]
    return error.get("status", f"http {response.status_code}")
