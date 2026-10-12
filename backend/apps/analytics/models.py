from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimeStampedModel
from apps.neighborhoods.models import Neighborhood


class AnalyticsSnapshot(UUIDTimeStampedModel):
    snapshot_type = models.CharField(max_length=80)
    neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.CASCADE,
        related_name="analytics_snapshots",
        null=True,
        blank=True,
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    metrics = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_analytics_snapshots",
        null=True,
        blank=True,
    )
    source_version = models.CharField(max_length=80, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["snapshot_type", "period_start", "period_end"]),
            models.Index(fields=["neighborhood", "snapshot_type"]),
            models.Index(fields=["generated_at"]),
        ]

    def __str__(self):
        return f"{self.snapshot_type}:{self.period_start:%Y-%m-%d}"

