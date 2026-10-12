"""Notification dispatch service and provider adapters.

Architecture
------------
Each *provider* knows how to deliver a single :class:`Notification` record via
one external channel (dashboard write, push, SMS).  Providers are lightweight —
they only flip ``status`` / ``sent_at`` on the notification row.

:class:`NotificationDispatchService` is the public façade used by the rest of
the codebase.  It handles:

* Creating ``Notification`` rows with preference-gating and rate-limiting.
* Queuing delivery via the ``send_notifications_batch`` Celery task.
* High-level helpers for incident alerts and SOS emergency contacts.
"""

import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Notification, NotificationPreference, NotificationTemplate


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres.

    Mirrors ``IncidentGeospatialService`` and the mobile client's ``AlarmRules``
    so that server and phone agree on what "within 5 km" means.
    """
    earth_radius = 6_371_000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ──────────────────────────────────────────────────────────────────────────────
# Provider layer
# ──────────────────────────────────────────────────────────────────────────────

# Rate-limit caps — configurable via NOTIFICATION_RATE_LIMIT_* in settings.
_RATE_LIMIT_MAX = getattr(settings, "NOTIFICATION_RATE_LIMIT_MAX", 20)
_RATE_LIMIT_WINDOW_MINUTES = getattr(settings, "NOTIFICATION_RATE_LIMIT_WINDOW_MINUTES", 60)


class BaseProvider:
    """Abstract delivery adapter.  Subclasses implement :meth:`deliver`."""

    def send(self, notification: Notification) -> bool:
        """Deliver *notification* and update its status in-place.  Returns True on success."""
        raise NotImplementedError

    def _mark_sent(self, notification: Notification) -> None:
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at", "updated_at", "last_modified_at"])

    def _mark_failed(self, notification: Notification, reason: str) -> None:
        notification.status = Notification.Status.FAILED
        notification.error_message = reason
        notification.retry_count = notification.retry_count + 1
        notification.save(update_fields=["status", "error_message", "retry_count", "updated_at", "last_modified_at"])


class InAppProvider(BaseProvider):
    """Dashboard (in-app) channel — the notification record IS the delivery."""

    def send(self, notification: Notification) -> bool:
        self._mark_sent(notification)
        return True


class PushProvider(BaseProvider):
    """FCM push channel.

    Sends a **data-only** message to each of the recipient's active devices, so
    the mobile app decides whether it alarms rather than letting the OS render
    a generic notification that bypasses the user's alarm rules.

    Delivery is best-effort per device: one dead handset must not fail the
    notification for the user's other devices.  Tokens that FCM reports as dead
    are deactivated so we stop paying for them.
    """

    def send(self, notification: Notification) -> bool:
        from apps.accounts.models import DeviceToken

        from .fcm import DEAD_TOKEN_ERRORS, FCMClient, FCMUnavailable

        if not notification.recipient_id:
            self._mark_failed(notification, "No recipient")
            return False

        tokens = list(
            DeviceToken.objects.filter(
                user_id=notification.recipient_id,
                is_active=True,
                deleted_at__isnull=True,
            )
        )
        if not tokens:
            self._mark_failed(notification, "No active device tokens for recipient")
            return False

        client = FCMClient()
        if not client.is_available():
            # Push is not configured on this deployment.  The mobile app polls
            # as a fallback, so this is a latency problem rather than a lost
            # alert — record it plainly instead of pretending we delivered.
            self._mark_failed(notification, "FCM is not configured on this server")
            return False

        payload = self._build_payload(notification)
        delivered_any = False
        dead_token_ids = []
        last_error = ""

        for device in tokens:
            try:
                delivered, detail = client.send(
                    token=device.token,
                    data=payload,
                    priority_high=notification.priority
                    in (Notification.Priority.HIGH, Notification.Priority.CRITICAL),
                )
            except FCMUnavailable as exc:
                last_error = str(exc)
                break

            if delivered:
                delivered_any = True
                device.last_seen_at = timezone.now()
                device.save(update_fields=["last_seen_at", "updated_at", "last_modified_at"])
            else:
                last_error = detail
                if detail in DEAD_TOKEN_ERRORS:
                    dead_token_ids.append(device.pk)

        if dead_token_ids:
            DeviceToken.objects.filter(pk__in=dead_token_ids).update(is_active=False)

        if delivered_any:
            self._mark_sent(notification)
            return True

        self._mark_failed(notification, last_error or "No device accepted the message")
        return False

    @staticmethod
    def _build_payload(notification: Notification) -> dict:
        """The data the client needs to decide whether to alarm.

        Note this is a *hint*, not a source of truth: the app re-fetches the
        incident over its authenticated session before acting, so a forged
        push cannot raise a siren on its own.
        """
        payload = {
            "kind": "sos_alert" if notification.sos_alert_id else "incident_alert",
            "notification_id": str(notification.pk),
            "title": notification.title,
            "body": notification.body,
            "priority": notification.priority,
        }

        if notification.incident_id:
            incident = notification.incident
            payload.update(
                {
                    "incident_id": str(notification.incident_id),
                    "severity": incident.severity,
                    "category": incident.category,
                    "latitude": str(incident.latitude),
                    "longitude": str(incident.longitude),
                    "occurred_at": incident.occurred_at.isoformat(),
                }
            )

        if notification.sos_alert_id:
            payload["sos_alert_id"] = str(notification.sos_alert_id)
            payload["latitude"] = str(notification.sos_alert.current_latitude)
            payload["longitude"] = str(notification.sos_alert.current_longitude)

        return payload


class SMSProvider(BaseProvider):
    """SMS channel via Twilio (stub).

    Validates recipient phone number exists, then marks sent.  A production
    implementation would call the Twilio REST API here.
    """

    def send(self, notification: Notification) -> bool:
        # Resolve phone number — prefer explicit payload override (used for
        # emergency contacts who may not be Users).
        phone = notification.payload.get("emergency_contact_phone")
        if not phone and notification.recipient_id:
            phone = getattr(notification.recipient, "phone_number", None)
        if not phone:
            self._mark_failed(notification, "No phone number available for SMS delivery")
            return False

        # Production: call Twilio client.messages.create(...) here.
        self._mark_sent(notification)
        return True


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch service
# ──────────────────────────────────────────────────────────────────────────────

class NotificationDispatchService:
    """Public façade for creating and queuing notifications."""

    PROVIDERS: dict[str, type[BaseProvider]] = {
        Notification.Channel.DASHBOARD: InAppProvider,
        Notification.Channel.PUSH: PushProvider,
        Notification.Channel.SMS: SMSProvider,
    }

    # ── Core dispatch ────────────────────────────────────────────────────────

    @classmethod
    def dispatch(
        cls,
        *,
        target_users,
        title: str,
        body: str,
        channel: str,
        priority: str = Notification.Priority.NORMAL,
        incident=None,
        sos_alert=None,
        payload: dict | None = None,
        bypass_rate_limit: bool = False,
    ) -> list[str]:
        """Create Notification rows for *target_users* and queue async delivery.

        Skips users who have opted out of *channel* or who have hit the rate
        limit for this channel in the current window (SOS alerts pass
        ``bypass_rate_limit`` -- a flood of reports must never silence a siren).

        Returns:
            List of notification UUIDs (as strings) that were queued.
        """
        from apps.notifications.tasks import send_notifications_batch

        payload = payload or {}
        notification_ids: list[str] = []

        for user in target_users:
            if not cls._channel_allowed(user, channel):
                continue
            if not bypass_rate_limit and not cls._within_rate_limit(user, channel):
                continue

            notif = Notification.objects.create(
                recipient=user,
                incident=incident,
                sos_alert=sos_alert,
                channel=channel,
                priority=priority,
                title=title,
                body=body,
                payload=payload,
                status=Notification.Status.QUEUED,
            )
            notification_ids.append(str(notif.pk))

        if notification_ids:
            send_notifications_batch.delay(notification_ids)

        return notification_ids

    # ── High-level helpers ────────────────────────────────────────────────────

    @classmethod
    def dispatch_incident_alert(cls, incident) -> None:
        """Notify everyone who should know about *incident*.

        The audience is the **union** of two groups:

        * members of the incident's neighbourhood, and
        * any user whose registered home coordinates fall within the
          neighbourhood's ``alert_radius_m`` of the incident.

        Membership alone is not enough: someone living two streets away but
        registered to the adjacent neighbourhood is exactly the person who
        needs this alert.  Distance alone is not enough either, because users
        who have never shared coordinates would be silently excluded.

        Uses a ``NotificationTemplate`` for ``incident_verified`` if one is
        configured; falls back to sensible defaults otherwise.
        """
        target_users = cls._incident_audience(incident)
        if not target_users:
            return

        context = {
            "title": incident.title,
            "category": incident.get_category_display(),
            "severity": incident.get_severity_display(),
            "address": incident.address or "unknown location",
        }
        template = NotificationTemplate.objects.filter(
            event_type=NotificationTemplate.EventType.INCIDENT_VERIFIED,
            is_active=True,
        ).first()

        if template:
            title = template.render_title(context)
            body = template.render_body(context)
            channels = template.channels or [Notification.Channel.DASHBOARD]
            priority = template.priority
        else:
            title = f"Incident Alert: {incident.title}"
            body = (
                f"A {incident.get_severity_display().lower()} {incident.get_category_display().lower()} "
                f"incident has been reported at {context['address']}."
            )
            # Push is included by default: without it the mobile app only
            # learns about an incident on its next poll, which is up to 15
            # minutes away when the app is backgrounded.
            channels = [Notification.Channel.DASHBOARD, Notification.Channel.PUSH]
            priority = (
                Notification.Priority.CRITICAL
                if incident.severity == "red"
                else Notification.Priority.HIGH
            )

        for channel in channels:
            cls.dispatch(
                target_users=target_users,
                title=title,
                body=body,
                channel=channel,
                priority=priority,
                incident=incident,
            )

    @classmethod
    def dispatch_sos_alert(cls, sos_alert) -> None:
        """Notify emergency contacts of an SOS alert via SMS.

        Each :class:`~apps.accounts.models.EmergencyContact` with
        ``can_receive_sos=True`` gets an SMS notification.  The contact's phone
        number is stored in ``payload`` because contacts are not ``User``
        instances.
        """
        from apps.accounts.models import EmergencyContact
        from apps.notifications.tasks import send_notifications_batch

        contacts = EmergencyContact.objects.filter(
            user=sos_alert.user,
            can_receive_sos=True,
            deleted_at__isnull=True,
        ).order_by("priority")

        location = (
            sos_alert.address
            or f"{sos_alert.current_latitude}, {sos_alert.current_longitude}"
        )
        notification_ids: list[str] = []

        for contact in contacts:
            notif = Notification.objects.create(
                recipient=sos_alert.user,
                sos_alert=sos_alert,
                channel=Notification.Channel.SMS,
                priority=Notification.Priority.CRITICAL,
                title="SOS Emergency Alert",
                body=(
                    f"EMERGENCY: {sos_alert.user.full_name} has triggered an SOS alert. "
                    f"Last known location: {location}."
                ),
                payload={
                    "emergency_contact_phone": contact.phone_number,
                    "contact_name": contact.name,
                },
                status=Notification.Status.QUEUED,
            )
            notification_ids.append(str(notif.pk))

        if notification_ids:
            send_notifications_batch.delay(notification_ids)

        cls.dispatch_sos_nearby(sos_alert)

    @classmethod
    def dispatch_sos_nearby(cls, sos_alert) -> list[str]:
        """Sound the alarm for everyone close to a new SOS alert.

        Sent on both the dashboard channel (open browser tabs and the mobile
        app's socket) and push (backgrounded phones), at CRITICAL priority.
        Users who switched ``sos_alerts`` off are respected; the sender never
        alarms themselves.
        """
        lat = float(sos_alert.current_latitude)
        lon = float(sos_alert.current_longitude)
        radius_m = float(getattr(settings, "SOS_ALERT_RADIUS_M", 2000))

        recipients = [
            user
            for user in cls._users_near(lat, lon, radius_m)
            if user.pk != sos_alert.user_id and cls._wants_sos_alerts(user)
        ]
        if not recipients:
            return []

        sender = sos_alert.user.full_name
        where = sos_alert.address or f"{sos_alert.current_latitude}, {sos_alert.current_longitude}"
        payload = {
            "kind": "sos_alert",
            "sos_alert_id": str(sos_alert.pk),
            "latitude": str(sos_alert.current_latitude),
            "longitude": str(sos_alert.current_longitude),
            "address": sos_alert.address,
            "sender_name": sender,
        }

        notification_ids: list[str] = []
        for channel in (Notification.Channel.DASHBOARD, Notification.Channel.PUSH):
            notification_ids += cls.dispatch(
                target_users=recipients,
                title="SOS: a neighbour needs help",
                body=f"{sender} has triggered an SOS alert near you. Location: {where}.",
                channel=channel,
                priority=Notification.Priority.CRITICAL,
                sos_alert=sos_alert,
                payload=payload,
                bypass_rate_limit=True,
            )
        return notification_ids

    @classmethod
    def broadcast_sos_ended(cls, sos_alert) -> None:
        """Tell everyone who was alarmed that the SOS is over, so sirens stop."""
        from apps.core.broadcasting import broadcast_sos_ended

        recipient_ids = set(
            Notification.objects.filter(
                sos_alert=sos_alert,
                channel=Notification.Channel.DASHBOARD,
                recipient__isnull=False,
            ).values_list("recipient_id", flat=True)
        )
        broadcast_sos_ended(sos_alert, recipient_ids)

    @classmethod
    def broadcast_incident_to_nearby(cls, incident) -> None:
        """Push a freshly reported incident onto the live map of everyone close by.

        Same audience as the incident alert (neighbourhood members plus anyone
        within the alert radius), but this is a silent map update, not an
        alarm, so it applies to every severity and creates no notification rows.
        """
        from apps.core.broadcasting import broadcast_incident_nearby

        broadcast_incident_nearby(incident, [user.pk for user in cls._incident_audience(incident)])

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _incident_audience(incident) -> list:
        """Users to alert about *incident*: neighbourhood members ∪ nearby residents."""
        from apps.accounts.models import User
        from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership

        audience = {}

        if incident.neighborhood_id:
            memberships = NeighborhoodMembership.objects.filter(
                neighborhood_id=incident.neighborhood_id,
                deleted_at__isnull=True,
            ).select_related("user")
            for membership in memberships:
                audience[membership.user_id] = membership.user

        radius_m = NotificationDispatchService._alert_radius_for(incident, Neighborhood)
        if radius_m:
            for user in NotificationDispatchService._users_near(
                float(incident.latitude), float(incident.longitude), radius_m
            ):
                audience.setdefault(user.pk, user)

        # Never alarm people about their own report.
        audience.pop(incident.reporter_id, None)
        return list(audience.values())

    @staticmethod
    def _users_near(lat: float, lon: float, radius_m: float) -> list:
        """Active users whose best-known location is within *radius_m* of the point.

        "Best known" is the device's recent fix if there is one, otherwise the
        registered home coordinates (see ``User.effective_location``).
        """
        from apps.accounts.models import User
        from apps.core.geo import box_q

        # Pre-filter with bounding boxes on both coordinate pairs so the
        # database does the bulk of the work; the exact circle and the
        # fresh-fix-versus-home choice are then applied in Python over a small
        # candidate set.
        candidates = User.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        ).filter(
            box_q("latitude", "longitude", lat, lon, radius_m)
            | box_q("last_latitude", "last_longitude", lat, lon, radius_m)
        )

        nearby = []
        for user in candidates:
            location = user.effective_location()
            if location and _haversine_m(lat, lon, location[0], location[1]) <= radius_m:
                nearby.append(user)
        return nearby

    @staticmethod
    def _alert_radius_for(incident, neighborhood_model) -> float:
        """The radius, in metres, within which residents are alerted."""
        if incident.neighborhood_id:
            radius = (
                neighborhood_model.objects.filter(pk=incident.neighborhood_id)
                .values_list("alert_radius_m", flat=True)
                .first()
            )
            if radius:
                return float(radius)
        return float(getattr(settings, "INCIDENT_ALERT_DEFAULT_RADIUS_M", 5000))

    @staticmethod
    def _wants_sos_alerts(user) -> bool:
        try:
            return user.notification_preferences.sos_alerts
        except NotificationPreference.DoesNotExist:
            return True

    @staticmethod
    def _channel_allowed(user, channel: str) -> bool:
        """Return True if the user has not opted out of *channel*."""
        try:
            pref = user.notification_preferences
            return pref.channel_enabled(channel)
        except NotificationPreference.DoesNotExist:
            return True

    @staticmethod
    def _within_rate_limit(user, channel: str) -> bool:
        """Return True if the user has not exceeded the per-channel rate limit."""
        cutoff = timezone.now() - timedelta(minutes=_RATE_LIMIT_WINDOW_MINUTES)
        count = Notification.objects.filter(
            recipient=user,
            channel=channel,
            created_at__gte=cutoff,
        ).count()
        return count < _RATE_LIMIT_MAX
