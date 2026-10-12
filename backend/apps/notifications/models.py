from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimeStampedModel


class Notification(UUIDTimeStampedModel):
    class Channel(models.TextChoices):
        PUSH = "push", "Push Notification"
        SMS = "sms", "SMS"
        DASHBOARD = "dashboard", "Dashboard Notification"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        READ = "read", "Read"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    incident = models.ForeignKey(
        "incidents.Incident",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    sos_alert = models.ForeignKey(
        "sos.SOSAlert",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    title = models.CharField(max_length=220)
    body = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["priority", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.channel}:{self.title}"


class NotificationPreference(UUIDTimeStampedModel):
    """Per-user opt-in settings for each notification channel and event type."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    dashboard_enabled = models.BooleanField(default=True)
    incident_alerts = models.BooleanField(default=True)
    sos_alerts = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"Preferences:{self.user_id}"

    def channel_enabled(self, channel: str) -> bool:
        return {
            Notification.Channel.PUSH: self.push_enabled,
            Notification.Channel.SMS: self.sms_enabled,
            Notification.Channel.DASHBOARD: self.dashboard_enabled,
        }.get(channel, True)


class NotificationTemplate(UUIDTimeStampedModel):
    """Templated message definitions for well-known event types.

    Title and body templates use Python str.format_map() with a context dict
    whose keys depend on the event type (e.g. ``{title}``, ``{severity}``).
    """

    class EventType(models.TextChoices):
        INCIDENT_VERIFIED = "incident_verified", "Incident Verified"
        INCIDENT_RESOLVED = "incident_resolved", "Incident Resolved"
        INCIDENT_ASSIGNED = "incident_assigned", "Incident Assigned"
        SOS_ALERT = "sos_alert", "SOS Alert"

    event_type = models.CharField(max_length=80, choices=EventType.choices, unique=True)
    title_template = models.CharField(max_length=220)
    body_template = models.TextField()
    priority = models.CharField(
        max_length=16,
        choices=Notification.Priority.choices,
        default=Notification.Priority.NORMAL,
    )
    channels = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["event_type", "is_active"])]

    def __str__(self):
        return self.event_type

    def render_title(self, context: dict) -> str:
        try:
            return self.title_template.format_map(context)
        except KeyError:
            return self.title_template

    def render_body(self, context: dict) -> str:
        try:
            return self.body_template.format_map(context)
        except KeyError:
            return self.body_template
