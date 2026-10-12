from rest_framework import serializers

from .models import SyncQueue


class SyncQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncQueue
        fields = [
            "id",
            "entity_type",
            "entity_id",
            "operation",
            "payload",
            "status",
            "local_modified_at",
            "synced_at",
            "retry_count",
            "last_error",
            "idempotency_key",
            "created_at",
        ]
        read_only_fields = fields


class SyncItemSerializer(serializers.Serializer):
    """One mutation submitted from an offline client."""

    entity_type = serializers.CharField(max_length=120)
    entity_id = serializers.UUIDField()
    operation = serializers.ChoiceField(choices=SyncQueue.Operation.choices)
    payload = serializers.JSONField(default=dict)
    local_modified_at = serializers.DateTimeField()
    idempotency_key = serializers.CharField(max_length=160)


class SyncPushSerializer(serializers.Serializer):
    """Batch of mutations submitted in a single sync push."""

    items = SyncItemSerializer(many=True, min_length=1)
