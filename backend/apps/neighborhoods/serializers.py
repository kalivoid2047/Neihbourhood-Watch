from rest_framework import serializers

from .models import Neighborhood, NeighborhoodMembership


class NeighborhoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Neighborhood
        fields = [
            "id",
            "name",
            "code",
            "city",
            "province",
            "centroid_latitude",
            "centroid_longitude",
            "alert_radius_m",
            "is_active",
        ]


class NeighborhoodCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Neighborhood
        fields = [
            "name",
            "code",
            "description",
            "city",
            "province",
            "boundary_geojson",
            "centroid_latitude",
            "centroid_longitude",
            "alert_radius_m",
        ]


class NeighborhoodMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    neighborhood_id = serializers.UUIDField(source="neighborhood.id", read_only=True)

    class Meta:
        model = NeighborhoodMembership
        fields = ["id", "user_id", "user_email", "user_full_name", "neighborhood_id", "role", "is_primary", "created_at"]


class NeighborhoodMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=NeighborhoodMembership.Role.choices)


# Re-exported so NeighborhoodViewSet only needs one import target.
from apps.incidents.serializers import NeighborhoodRiskSummarySerializer  # noqa: E402, F401
