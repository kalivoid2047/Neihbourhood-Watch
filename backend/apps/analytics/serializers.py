from rest_framework import serializers

from .models import AnalyticsSnapshot


class AnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsSnapshot
        fields = [
            "id",
            "snapshot_type",
            "neighborhood",
            "period_start",
            "period_end",
            "metrics",
            "generated_at",
            "source_version",
        ]
        read_only_fields = fields
