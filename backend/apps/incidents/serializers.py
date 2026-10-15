from rest_framework import serializers
from django.utils import timezone

from apps.accounts.models import User

from .models import Incident, IncidentMedia


class IncidentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    reporter_name = serializers.CharField(source="reporter.full_name", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "reporter",
            "reporter_name",
            "title",
            "category",
            "category_display",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "latitude",
            "longitude",
            "address",
            "occurred_at",
            "created_at",
        ]
        read_only_fields = fields


class IncidentSerializer(serializers.ModelSerializer):
    """Full incident detail serializer."""

    reporter_name = serializers.CharField(source="reporter.full_name", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    media = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id",
            "reporter",
            "reporter_name",
            "neighborhood",
            "title",
            "description",
            "category",
            "category_display",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "latitude",
            "longitude",
            "address",
            "occurred_at",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "assigned_to",
            "assigned_to_name",
            "metadata",
            "sync_version",
            "media",
            "created_at",
            "updated_at",
            "last_modified_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "reporter_name",
            "status",
            "status_display",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "sync_version",
            "media",
            "created_at",
            "updated_at",
            "last_modified_at",
        ]

    def get_media(self, obj):
        media_qs = obj.media.filter(deleted_at__isnull=True)
        return IncidentMediaSerializer(media_qs, many=True).data


class IncidentCreateSerializer(serializers.ModelSerializer):
    """Serializer for incident creation."""

    class Meta:
        model = Incident
        fields = [
            "id",
            "neighborhood",
            "title",
            "description",
            "category",
            "severity",
            "latitude",
            "longitude",
            "address",
            "occurred_at",
            "metadata",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        validated_data["reporter"] = self.context["request"].user
        return super().create(validated_data)


class IncidentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for incident updates (reporter updates before verification)."""

    class Meta:
        model = Incident
        fields = [
            "title",
            "description",
            "category",
            "severity",
            "latitude",
            "longitude",
            "address",
            "occurred_at",
            "metadata",
        ]


class IncidentStatusTransitionSerializer(serializers.Serializer):
    """Serializer for incident status transitions."""

    new_status = serializers.ChoiceField(choices=Incident.Status.choices)


class IncidentAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning incidents."""

    assigned_to_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_assigned_to_id(self, value):
        if value is None:
            return None
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return value


class IncidentMediaListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for media in lists."""

    media_type_display = serializers.CharField(source="get_media_type_display", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = IncidentMedia
        fields = [
            "id",
            "media_type",
            "media_type_display",
            "original_filename",
            "size_bytes",
            "uploaded_by_name",
            "uploaded_at",
        ]
        read_only_fields = fields


class IncidentMediaSerializer(serializers.ModelSerializer):
    """Full media detail serializer."""

    media_type_display = serializers.CharField(source="get_media_type_display", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = IncidentMedia
        fields = [
            "id",
            "incident",
            "uploaded_by",
            "uploaded_by_name",
            "media_type",
            "media_type_display",
            "file",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum",
            "metadata",
            "uploaded_at",
        ]
        read_only_fields = ["uploaded_at"]


class IncidentMediaUploadSerializer(serializers.Serializer):
    """Serializer for media upload."""

    media_type = serializers.ChoiceField(choices=IncidentMedia.MediaType.choices)
    file = serializers.FileField()
    metadata = serializers.JSONField(required=False, default=dict)

    # Allowed MIME type prefixes for each IncidentMedia.MediaType value.
    _ALLOWED_MIME_PREFIXES = {
        "image": ("image/",),
        "video": ("video/",),
        "audio": ("audio/",),
    }

    def validate_file(self, value):
        if value.size > 100 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 100MB.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        file_obj = attrs.get("file")
        media_type = attrs.get("media_type")
        if file_obj and media_type:
            from apps.core.mime import detect_mime

            header = file_obj.read(2048)
            file_obj.seek(0)
            detected_mime = detect_mime(header)
            allowed_prefixes = self._ALLOWED_MIME_PREFIXES.get(media_type, ())
            if not detected_mime or not any(detected_mime.startswith(p) for p in allowed_prefixes):
                raise serializers.ValidationError(
                    {
                        "file": (
                            f"File content does not match media type '{media_type}' "
                            f"(detected: {detected_mime or 'unknown'})."
                        )
                    }
                )
        return attrs


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4: Geospatial serializers
# ──────────────────────────────────────────────────────────────────────────────


class NearbyIncidentSerializer(IncidentListSerializer):
    """Extends the list serializer with a distance_m annotation."""

    distance_m = serializers.SerializerMethodField()

    class Meta(IncidentListSerializer.Meta):
        fields = IncidentListSerializer.Meta.fields + ["distance_m"]
        read_only_fields = fields

    def get_distance_m(self, obj):
        return round(getattr(obj, "_distance_m", 0.0), 1)


class HeatmapCellSerializer(serializers.Serializer):
    """One grid cell in the incident heatmap response."""

    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    count = serializers.IntegerField()
    severity_counts = serializers.DictField(child=serializers.IntegerField())


class NeighborhoodRiskSummarySerializer(serializers.Serializer):
    """Risk-metric summary for a neighborhood."""

    neighborhood_id = serializers.UUIDField()
    days = serializers.IntegerField()
    total_incidents = serializers.IntegerField()
    by_severity = serializers.DictField(child=serializers.IntegerField())
    by_category = serializers.DictField(child=serializers.IntegerField())
    by_status = serializers.DictField(child=serializers.IntegerField())

