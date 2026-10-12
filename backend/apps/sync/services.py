"""Sync push service — applies offline mutations from mobile clients.

Supported entity types
----------------------
``incident``  — create / update / delete operations on the Incident model.

Unknown entity types are stored as PENDING in the SyncQueue for later manual
or automated processing (e.g., a future IoT sensor entity type).

Conflict detection
------------------
For UPDATE operations the server compares ``local_modified_at`` (the timestamp
the client last touched the record) against the server's ``last_modified_at``.
If the server record is newer, the item is stored with status=CONFLICT so the
client can fetch the latest version and resolve the discrepancy.
"""

from django.db import IntegrityError, OperationalError
from django.utils import timezone

from .models import SyncQueue


class SyncPushService:
    """Process a batch of offline mutations from a single authenticated user."""

    @classmethod
    def push(cls, user, items: list[dict]) -> list[dict]:
        results = []
        for item in items:
            result = cls._apply_one(user, item)
            results.append(result)
        return results

    @classmethod
    def _apply_one(cls, user, item: dict) -> dict:
        key = item["idempotency_key"]
        existing = SyncQueue.objects.filter(idempotency_key=key).first()
        if existing and existing.status == SyncQueue.Status.SYNCED:
            return {
                "idempotency_key": key,
                "status": "already_synced",
                "entity_id": str(item["entity_id"]),
                "error": None,
            }

        handler = cls._get_handler(item["entity_type"])
        try:
            status, error = handler(user, item)
        except (KeyError, ValueError, TypeError, AttributeError, IntegrityError, OperationalError) as exc:
            status = SyncQueue.Status.FAILED
            error = str(exc)

        queue_row = SyncQueue.objects.update_or_create(
            idempotency_key=key,
            defaults={
                "user": user,
                "entity_type": item["entity_type"],
                "entity_id": item["entity_id"],
                "operation": item["operation"],
                "payload": item.get("payload", {}),
                "local_modified_at": item["local_modified_at"],
                "status": status,
                "synced_at": timezone.now() if status == SyncQueue.Status.SYNCED else None,
                "last_error": error or "",
            },
        )[0]

        return {
            "idempotency_key": key,
            "status": status,
            "entity_id": str(item["entity_id"]),
            "error": error,
        }

    @classmethod
    def _get_handler(cls, entity_type: str):
        return {
            "incident": cls._handle_incident,
        }.get(entity_type, cls._handle_unknown)

    @staticmethod
    def _handle_unknown(user, item) -> tuple[str, str | None]:
        return SyncQueue.Status.PENDING, None

    @staticmethod
    def _handle_incident(user, item) -> tuple[str, str | None]:
        from apps.incidents.models import Incident

        operation = item["operation"]
        entity_id = item["entity_id"]
        payload = item.get("payload", {})
        local_modified_at = item["local_modified_at"]

        if operation == SyncQueue.Operation.CREATE:
            if Incident.objects.filter(pk=entity_id).exists():
                return SyncQueue.Status.SYNCED, None
            payload.setdefault("reporter_id", str(user.pk))
            Incident.objects.create(id=entity_id, reporter=user, **payload)
            return SyncQueue.Status.SYNCED, None

        if operation == SyncQueue.Operation.UPDATE:
            try:
                incident = Incident.objects.get(pk=entity_id)
            except Incident.DoesNotExist:
                return SyncQueue.Status.FAILED, "Incident not found"

            if incident.last_modified_at and incident.last_modified_at > local_modified_at:
                return SyncQueue.Status.CONFLICT, "Server version is newer"

            allowed = {"title", "description", "category", "severity", "address", "occurred_at"}

            # Validate choice fields before applying to prevent storing invalid enum values.
            if "category" in payload:
                valid_categories = {c for c, _ in Incident.Category.choices}
                if payload["category"] not in valid_categories:
                    return SyncQueue.Status.FAILED, f"Invalid category: {payload['category']!r}"
            if "severity" in payload:
                valid_severities = {s for s, _ in Incident.Severity.choices}
                if payload["severity"] not in valid_severities:
                    return SyncQueue.Status.FAILED, f"Invalid severity: {payload['severity']!r}"

            update_fields = [f for f in payload if f in allowed]
            for field in update_fields:
                setattr(incident, field, payload[field])
            incident.save(update_fields=[*update_fields, "updated_at", "last_modified_at"])
            return SyncQueue.Status.SYNCED, None

        if operation == SyncQueue.Operation.DELETE:
            Incident.objects.filter(pk=entity_id, reporter=user).update(deleted_at=timezone.now())
            return SyncQueue.Status.SYNCED, None

        return SyncQueue.Status.FAILED, f"Unknown operation: {operation}"
