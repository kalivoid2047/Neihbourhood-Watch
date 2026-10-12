from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import UUIDTimeStampedModel
from apps.neighborhoods.models import Neighborhood


class SOSAlert(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ESCALATED = "escalated", "Escalated"
        RESOLVED = "resolved", "Resolved"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sos_alerts")
    neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.SET_NULL,
        related_name="sos_alerts",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    current_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    current_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    address = models.TextField(blank=True)
    audio_recording = models.FileField(upload_to="sos-audio/%Y/%m/", blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["neighborhood", "status"]),
            models.Index(fields=["current_latitude", "current_longitude"]),
        ]

    def __str__(self):
        return f"{self.user}:{self.status}:{self.started_at}"


class SOSLocationPing(UUIDTimeStampedModel):
    sos_alert = models.ForeignKey(SOSAlert, on_delete=models.CASCADE, related_name="location_pings")
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    captured_at = models.DateTimeField()

    class Meta:
        ordering = ("captured_at",)
        indexes = [
            models.Index(fields=["sos_alert", "captured_at"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.sos_alert_id}:{self.captured_at}"

