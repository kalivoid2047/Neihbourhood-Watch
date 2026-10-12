"""Phase 6: WebSocket consumer tests.

Strategy
--------
Each connect/disconnect test runs a self-contained coroutine via
``asyncio.run()``.  We test only the connect/reject outcome rather than
in-loop message passing, which avoids the statefulness problems that arise
when the InMemoryChannelLayer's internal asyncio.Queues span multiple
``asyncio.run()`` invocations (each call creates a separate event loop).

Broadcasting helpers are tested synchronously with a real channel layer –
they only need to confirm the call doesn't raise, not that the remote socket
received the frame.
"""

import asyncio
import uuid
from unittest import mock

from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.core.broadcasting import broadcast_incident_update, broadcast_notification
from apps.incidents.models import Incident
from apps.neighborhoods.models import Neighborhood
from apps.notifications.models import Notification

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_UID = 0


def _inc():
    global _UID
    _UID += 1
    return _UID


def make_user(role_code=None):
    from apps.accounts.models import Role

    n = _inc()
    extra = {}
    if role_code:
        extra["role"] = Role.objects.get_or_create(
            code=role_code, defaults={"name": Role.Code(role_code).label, "is_system": True}
        )[0]
    return User.objects.create_user(
        email=f"ws_u{n}@test.invalid",
        full_name=f"WS User {n}",
        phone_number=f"+2637701{n:05d}",
        national_id=f"71{n:07d}A00",
        password="Pass123!",
        **extra,
    )


def get_application():
    """Return a URLRouter-only application for testing.

    We bypass AllowedHostsOriginValidator because WebsocketCommunicator
    sends no Origin header, which the validator would reject.
    """
    from channels.routing import URLRouter
    from apps.core.routing import websocket_urlpatterns
    return URLRouter(websocket_urlpatterns)


async def connect_state(comm, timeout=5):
    """Return ``(open, close_code)`` as a browser would observe it.

    Rejections accept the handshake and then close with a custom code, so
    "connected" alone is not enough: a rejected socket is one that is followed
    by a ``websocket.close`` frame.
    """
    connected, _ = await comm.connect(timeout=timeout)
    if not connected:
        return False, None
    # receive_nothing() (unlike receive_output) doesn't cancel the app on timeout.
    if await comm.receive_nothing(timeout=0.3):
        return True, None
    message = await comm.receive_output(timeout=1)
    if message.get("type") == "websocket.close":
        return False, message.get("code")
    return True, None


# ──────────────────────────────────────────────────────────────────────────────
# Incident consumer — connection tests
# ──────────────────────────────────────────────────────────────────────────────

class IncidentConsumerAuthTests(TransactionTestCase):
    """Each test gets an isolated asyncio event loop via asyncio.run().

    TransactionTestCase (vs TestCase) means DB rows are committed, so the
    thread-pool workers spawned by database_sync_to_async can see them.
    """

    def setUp(self):
        from django.utils import timezone
        from apps.accounts.models import Role

        self.user = make_user(Role.Code.RESIDENT)
        self.token = str(AccessToken.for_user(self.user))
        # The user reported this incident, so they are allowed to watch it.
        self.incident_id = Incident.objects.create(
            reporter=self.user, title="WS", description="d",
            category=Incident.Category.THEFT, latitude="0.0", longitude="0.0",
            occurred_at=timezone.now(),
        ).pk

    def test_connect_with_valid_token(self):
        token = self.token
        incident_id = self.incident_id
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, f"/ws/incidents/{incident_id}/?token={token}")
            connected, code = await connect_state(comm)
            self.assertTrue(connected, f"Expected successful WebSocket connection (closed with {code})")
            await comm.disconnect()

        asyncio.run(_t())

    def test_connect_without_token_rejected(self):
        incident_id = self.incident_id
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, f"/ws/incidents/{incident_id}/")
            connected, code = await connect_state(comm)
            self.assertFalse(connected, "Expected WebSocket rejection")
            self.assertEqual(code, 4001)

        asyncio.run(_t())

    def test_connect_with_invalid_token_rejected(self):
        incident_id = self.incident_id
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, f"/ws/incidents/{incident_id}/?token=bad.jwt.here")
            connected, code = await connect_state(comm)
            self.assertFalse(connected, "Expected WebSocket rejection")
            self.assertEqual(code, 4001)

        asyncio.run(_t())


# ──────────────────────────────────────────────────────────────────────────────
# Notification consumer — connection tests
# ──────────────────────────────────────────────────────────────────────────────

class NotificationConsumerAuthTests(TransactionTestCase):
    def setUp(self):
        self.user = make_user()
        self.token = str(AccessToken.for_user(self.user))

    def test_connect_with_valid_token(self):
        token = self.token
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, f"/ws/notifications/?token={token}")
            connected, code = await connect_state(comm)
            self.assertTrue(connected, f"Expected successful WebSocket connection (closed with {code})")
            await comm.disconnect()

        asyncio.run(_t())

    def test_connect_without_token_rejected(self):
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, "/ws/notifications/")
            connected, code = await connect_state(comm)
            self.assertFalse(connected, "Expected WebSocket rejection")
            self.assertEqual(code, 4001)

        asyncio.run(_t())

    def test_connect_with_invalid_token_rejected(self):
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, "/ws/notifications/?token=garbage")
            connected, code = await connect_state(comm)
            self.assertFalse(connected, "Expected WebSocket rejection")
            self.assertEqual(code, 4001)

        asyncio.run(_t())


# ──────────────────────────────────────────────────────────────────────────────
# Broadcasting helper smoke-tests
# ──────────────────────────────────────────────────────────────────────────────

class BroadcastHelperTests(TestCase):
    """Confirm that broadcast_* helpers never raise, even in edge cases."""

    def setUp(self):
        from django.utils import timezone
        self.user = make_user()
        self.neighborhood = Neighborhood.objects.create(
            name="Broadcast Hood",
            code="broadcast-hood",
            city="Harare",
            province="Harare",
            is_active=True,
        )
        self.incident = Incident.objects.create(
            reporter=self.user,
            neighborhood=self.neighborhood,
            title="Broadcast Test",
            description="desc",
            category=Incident.Category.THEFT,
            severity=Incident.Severity.YELLOW,
            status=Incident.Status.PENDING,
            latitude="0.0",
            longitude="0.0",
            occurred_at=timezone.now(),
        )
        self.notification = Notification.objects.create(
            recipient=self.user,
            channel=Notification.Channel.DASHBOARD,
            title="Notif",
            body="body",
            priority=Notification.Priority.NORMAL,
        )

    def test_broadcast_incident_update_does_not_raise(self):
        broadcast_incident_update(self.incident)

    def test_incident_payload_is_plain_json_types(self):
        """UUID/Decimal/datetime values must be converted before hitting a channel layer."""
        import json

        with mock.patch("apps.core.broadcasting._send") as send:
            broadcast_incident_update(self.incident)
        group, message = send.call_args_list[0].args
        self.assertEqual(group, f"incident_{self.incident.pk}")
        # Raises TypeError if any UUID/Decimal/datetime object slipped through.
        json.dumps(message)
        self.assertEqual(message["incident"]["id"], str(self.incident.pk))
        self.assertEqual(message["incident"]["reporter"], str(self.user.pk))

    def test_broadcast_notification_does_not_raise(self):
        broadcast_notification(self.notification)

    def test_broadcast_incident_no_neighborhood_does_not_raise(self):
        self.incident.neighborhood = None
        broadcast_incident_update(self.incident)

    def test_broadcast_notification_no_recipient_does_not_raise(self):
        self.notification.recipient = None
        broadcast_notification(self.notification)

    def test_broadcast_silenced_when_channel_layer_missing(self):
        with mock.patch("apps.core.broadcasting._get_layer", return_value=None):
            broadcast_incident_update(self.incident)
            broadcast_notification(self.notification)


# ──────────────────────────────────────────────────────────────────────────────
# Incident consumer — per-incident authorization
# ──────────────────────────────────────────────────────────────────────────────

class IncidentConsumerAuthorizationTests(TransactionTestCase):
    """An authenticated user may only watch incidents the REST API would show them."""

    def setUp(self):
        from django.utils import timezone
        from apps.accounts.models import Role
        from apps.neighborhoods.models import NeighborhoodMembership

        self.reporter = make_user(Role.Code.RESIDENT)
        self.member = make_user(Role.Code.RESIDENT)
        self.outsider = make_user(Role.Code.RESIDENT)
        self.admin = make_user(Role.Code.SYSTEM_ADMIN)
        self.no_role = make_user()

        hood = Neighborhood.objects.create(name="WS Hood", code="ws-hood", city="Harare", province="Harare")
        NeighborhoodMembership.objects.create(user=self.member, neighborhood=hood)
        self.incident = Incident.objects.create(
            reporter=self.reporter, neighborhood=hood, title="Private-ish", description="d",
            category=Incident.Category.THEFT, latitude="0.0", longitude="0.0",
            occurred_at=timezone.now(),
        )

    def _connect(self, user, incident_id=None):
        token = str(AccessToken.for_user(user))
        path = f"/ws/incidents/{incident_id or self.incident.pk}/?token={token}"
        app = get_application()

        async def _t():
            comm = WebsocketCommunicator(app, path)
            connected, code = await connect_state(comm)
            if connected:
                await comm.disconnect()
            return connected, code

        return asyncio.run(_t())

    def test_reporter_allowed(self):
        self.assertTrue(self._connect(self.reporter)[0])

    def test_neighborhood_member_allowed(self):
        self.assertTrue(self._connect(self.member)[0])

    def test_admin_allowed(self):
        self.assertTrue(self._connect(self.admin)[0])

    def test_outsider_rejected_with_4003(self):
        connected, code = self._connect(self.outsider)
        self.assertFalse(connected)
        self.assertEqual(code, 4003)

    def test_user_without_role_rejected(self):
        self.assertFalse(self._connect(self.no_role)[0])

    def test_unknown_incident_rejected_same_code_as_forbidden(self):
        connected, code = self._connect(self.admin, incident_id=uuid.uuid4())
        self.assertFalse(connected)
        self.assertEqual(code, 4003)
