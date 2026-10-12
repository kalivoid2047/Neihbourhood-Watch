"""Django Channels WebSocket consumers.

Authentication
--------------
Both consumers expect a JWT access token as a ``?token=`` query-string
parameter.  This avoids the header-injection complexities of the WebSocket
handshake while keeping auth consistent with the REST API.

  ws://host/ws/incidents/<uuid>/?token=<access>
  ws://host/ws/notifications/?token=<access>

An unauthenticated connection is closed with code 4001.  An
authenticated user who may not view the requested incident (or asks for one that
does not exist) is closed with code 4003; both cases share the code so the
socket cannot be used to probe which incident IDs exist.

Rejections *accept the handshake and then close* with the custom code.  Closing
before ``accept()`` makes the server answer the upgrade with a bare HTTP 403,
which browsers surface as close code 1006 -- the client would never see 4001 or
4003 and could not tell an expired token from a network failure.

Channel groups
--------------
``IncidentConsumer``  joins ``incident_<incident_id>`` so that any service code
(or Celery task) can push ``incident.updated`` events to everyone watching a
single incident.

``NotificationConsumer`` joins ``user_notifications_<user_id>`` for personal
notification delivery.
"""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


async def _authenticate(scope):
    """Return the User for the JWT in the query string, or None."""
    qs_raw = scope.get("query_string", b"")
    params = parse_qs(qs_raw.decode(errors="replace"))
    tokens = params.get("token", [])
    if not tokens:
        return None

    try:
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(tokens[0])
        User = get_user_model()
        return await database_sync_to_async(User.objects.select_related("role").get)(
            pk=token["user_id"], deleted_at__isnull=True
        )
    except Exception:  # noqa: BLE001
        return None


@database_sync_to_async
def _can_view_incident(user, incident_id):
    from apps.incidents.models import Incident
    from apps.incidents.permissions import user_can_view_incident

    incident = Incident.objects.filter(pk=incident_id).first()
    return incident is not None and user_can_view_incident(user, incident)


class _RejectMixin:
    async def reject(self, code):
        """Complete the handshake, then close with ``code`` so the client can read it."""
        await self.accept()
        await self.close(code=code)


class IncidentConsumer(_RejectMixin, AsyncWebsocketConsumer):
    """Real-time updates for a single incident."""

    async def connect(self):
        self.user = await _authenticate(self.scope)
        if self.user is None:
            await self.reject(4001)
            return

        self.incident_id = str(self.scope["url_route"]["kwargs"]["incident_id"])
        if not await _can_view_incident(self.user, self.incident_id):
            await self.reject(4003)
            return

        self.group_name = f"incident_{self.incident_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients don't send commands on this channel; ignore any messages.
        pass

    # ── Group message handlers (called by channel_layer.group_send) ────────

    async def incident_updated(self, event):
        await self.send(text_data=json.dumps({"type": "incident_updated", "incident": event["incident"]}))


class NotificationConsumer(_RejectMixin, AsyncWebsocketConsumer):
    """Personal notification stream for the authenticated user."""

    async def connect(self):
        self.user = await _authenticate(self.scope)
        if self.user is None:
            await self.reject(4001)
            return

        self.group_name = f"user_notifications_{self.user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    # ── Group message handlers ─────────────────────────────────────────────

    async def notification_created(self, event):
        await self.send(text_data=json.dumps({"type": "notification_created", "notification": event["notification"]}))

    async def incident_nearby(self, event):
        await self.send(text_data=json.dumps({"type": "incident_nearby", "incident": event["incident"]}))

    async def sos_ended(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "sos_ended", "sos_alert_id": event["sos_alert_id"], "status": event["status"]}
            )
        )
