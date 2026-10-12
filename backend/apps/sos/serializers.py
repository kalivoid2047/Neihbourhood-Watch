from rest_framework import serializers

from .models import SOSAlert, SOSLocationPing


class SOSLocationPingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOSLocationPing
        fields = ["id", "latitude", "longitude", "accuracy_m", "captured_at"]


class SOSAlertSerializer(serializers.ModelSerializer):
    location_pings = SOSLocationPingSerializer(many=True, read_only=True)

    class Meta:
        model = SOSAlert
        fields = [
            "id",
            "user",
            "neighborhood",
            "status",
            "started_at",
            "ended_at",
            "current_latitude",
            "current_longitude",
            "address",
            "audio_recording",
            "metadata",
            "location_pings",
        ]

