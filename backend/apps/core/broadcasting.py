"""Thin sync→async helpers for pushing events to WebSocket channel groups.

All functions are safe to call from synchronous Django views, Celery tasks, and
service-layer code.  If the channel layer is not configured (e.g. in a plain
WSGI dev setup) or the send fails, the call is silently swallowed so the
caller's primary flow is never interrupted.
"""

import json

from asgiref.sync import async_to_sync
from django.core.serializers.json import DjangoJSONEncoder


def _get_layer():
    try:
        from channels.layers import get_channel_layer
        return get_channel_layer()
    except ImportError:
        return None


def _send(group: str, message: dict) -> None:
    layer = _get_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, message)
    except Exception:  # noqa: BLE001
        pass


def _json_safe(data):
    """Round-trip through JSON so the payload holds only plain str/int/float/bool/None/list/dict.

    Serializer output contains UUID, Decimal and datetime objects.  Channel
    layers serialize messages themselves (msgpack for Redis) and cannot encode
    those, and the consumer's ``json.dumps`` would raise on them -- either way
    the live update is lost.
    """
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


# ── Public broadcast functions ────────────────────────────────────────────────

def broadcast_incident_update(incident) -> None:
    """Push an incident_updated event to all subscribers of that incident."""
    from apps.incidents.serializers import IncidentSerializer

    payload = _json_safe(IncidentSerializer(incident).data)
    # Notify per-incident watchers (e.g. incident-detail page)
    _send(
        f"incident_{incident.pk}",
        {"type": "incident.updated", "incident": payload},
    )
    # Notify neighborhood-level watchers (e.g. incidents list page)
    if incident.neighborhood_id:
        _send(
            f"neighborhood_incidents_{incident.neighborhood_id}",
            {"type": "incident.updated", "incident": payload},
        )


def broadcast_notification(notification) -> None:
    """Push a notification_created event to the recipient's personal group."""
    if not notification.recipient_id:
        return
    _send(
        f"user_notifications_{notification.recipient_id}",
        {
            "type": "notification.created",
            "notification": {
                "id": str(notification.pk),
                "title": notification.title,
                "body": notification.body,
                "channel": notification.channel,
                "priority": notification.priority,
                "created_at": notification.created_at.isoformat(),
                # Lets the client tell an SOS siren from an ordinary notice and
                # point at the map without a second request.
                "payload": _json_safe(notification.payload or {}),
            },
        },
    )


def broadcast_incident_nearby(incident, user_ids) -> None:
    """Push a new incident onto the live map of each user in *user_ids*."""
    from apps.incidents.serializers import IncidentListSerializer

    payload = _json_safe(IncidentListSerializer(incident).data)
    for user_id in user_ids:
        _send(
            f"user_notifications_{user_id}",
            {"type": "incident.nearby", "incident": payload},
        )


def broadcast_sos_ended(sos_alert, user_ids) -> None:
    """Tell each user in *user_ids* that an SOS alert is over (stop the siren)."""
    for user_id in user_ids:
        _send(
            f"user_notifications_{user_id}",
            {
                "type": "sos.ended",
                "sos_alert_id": str(sos_alert.pk),
                "status": sos_alert.status,
            },
        )
