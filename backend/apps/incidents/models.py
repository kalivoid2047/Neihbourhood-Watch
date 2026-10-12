from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import UUIDTimeStampedModel
from apps.neighborhoods.models import Neighborhood


class Incident(UUIDTimeStampedModel):
    class Category(models.TextChoices):
        THEFT = "theft", "Theft"
        BURGLARY = "burglary", "Burglary"
        ASSAULT = "assault", "Assault"
        SUSPICIOUS_ACTIVITY = "suspicious_activity", "Suspicious Activity"
        MISSING_PERSON = "missing_person", "Missing Person"
        VANDALISM = "vandalism", "Vandalism"
        INFRASTRUCTURE_DAMAGE = "infrastructure_damage", "Infrastructure Damage"

    class Severity(models.TextChoices):
        RED = "red", "Critical"
        YELLOW = "yellow", "Important"
        BLUE = "blue", "Average"
        GREEN = "green", "Normal"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        INVESTIGATING = "investigating", "Investigating"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_incidents",
    )
    neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.SET_NULL,
        related_name="incidents",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=220)
    description = models.TextField()
    category = models.CharField(max_length=32, choices=Category.choices)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.GREEN)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
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
    address = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_incidents",
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_incidents",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    sync_version = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["severity", "status"]),
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["neighborhood", "status"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["last_modified_at"]),
        ]

    def __str__(self):
        return self.title


class IncidentMedia(UUIDTimeStampedModel):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="media")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_incident_media",
    )
    media_type = models.CharField(max_length=12, choices=MediaType.choices)
    file = models.FileField(upload_to="incident-evidence/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120)
    size_bytes = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=128, blank=True)
    encryption_key_id = models.CharField(max_length=160, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["incident", "media_type"]),
            models.Index(fields=["checksum"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.incident_id}:{self.media_type}"

