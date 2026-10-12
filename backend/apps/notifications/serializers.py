from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "incident",
            "sos_alert",
            "channel",
            "status",
            "priority",
            "title",
            "body",
            "payload",
            "sent_at",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "push_enabled",
            "sms_enabled",
            "dashboard_enabled",
            "incident_alerts",
            "sos_alerts",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

