from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimeStampedModel


class SyncQueue(UUIDTimeStampedModel):
    class Operation(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SYNCED = "synced", "Synced"
        FAILED = "failed", "Failed"
        CONFLICT = "conflict", "Conflict"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_items")
    entity_type = models.CharField(max_length=120)
    entity_id = models.UUIDField()
    operation = models.CharField(max_length=12, choices=Operation.choices)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    local_modified_at = models.DateTimeField()
    synced_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["status", "local_modified_at"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self):
        return f"{self.operation}:{self.entity_type}:{self.entity_id}"

