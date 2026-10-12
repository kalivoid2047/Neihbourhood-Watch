"""SOS alert API views."""

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.models import Role
from apps.incidents.services import _haversine_m
from apps.neighborhoods.models import Neighborhood

from .models import SOSAlert, SOSLocationPing
from .serializers import SOSAlertSerializer, SOSLocationPingSerializer


def _parse_coordinates(data: dict, lat_key: str, lon_key: str) -> tuple[float, float]:
    """Parse and range-validate lat/lon from a request data dict.

    Raises ``ValidationError`` with field-keyed errors on failure.
    """
    try:
        lat = float(data[lat_key])
        lon = float(data[lon_key])
    except (KeyError, TypeError, ValueError):
        raise ValidationError({lat_key: "This field is required and must be a number."})
    if not (-90 <= lat <= 90):
        raise ValidationError({lat_key: "Must be between -90 and 90."})
    if not (-180 <= lon <= 180):
        raise ValidationError({lon_key: "Must be between -180 and 180."})
    return lat, lon


def _resolve_neighborhood(user, lat: float, lon: float):
    """Pick the neighborhood an SOS alert belongs to.

    Derived server-side (never client-supplied) so responders scoped to a
    neighborhood actually see the alert:

    1. the user's primary membership,
    2. otherwise any of their memberships,
    3. otherwise the nearest active neighborhood whose alert radius covers the point.
    """
    memberships = user.neighborhood_memberships.select_related("neighborhood").filter(
        neighborhood__is_active=True
    )
    membership = memberships.filter(is_primary=True).first() or memberships.order_by("created_at").first()
    if membership:
        return membership.neighborhood

    nearest, nearest_dist = None, None
    candidates = Neighborhood.objects.filter(
        is_active=True, centroid_latitude__isnull=False, centroid_longitude__isnull=False
    )
    for hood in candidates:
        dist = _haversine_m(lat, lon, hood.centroid_latitude, hood.centroid_longitude)
        if dist <= hood.alert_radius_m and (nearest_dist is None or dist < nearest_dist):
            nearest, nearest_dist = hood, dist
    return nearest


class SOSAlertViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """
    SOS alert lifecycle.

    POST /api/sos/              — create (authenticated user)
    GET  /api/sos/              — list own alerts
    GET  /api/sos/{id}/         — detail
    POST /api/sos/{id}/ping/    — add location ping
    POST /api/sos/{id}/resolve/ — resolve alert
    POST /api/sos/{id}/cancel/  — cancel alert
    GET  /api/sos/active/       — list active alerts (coordinator/police/admin)
    """

    serializer_class = SOSAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.role_id:
            return SOSAlert.objects.none()
        role_code = user.role.code
        if role_code in (Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN, Role.Code.POLICE_OFFICER):
            return SOSAlert.objects.all().order_by("-created_at")
        return SOSAlert.objects.filter(user=user).order_by("-created_at")

    def create(self, request):
        """Create an SOS alert and dispatch emergency contact notifications."""
        lat, lon = _parse_coordinates(request.data, "current_latitude", "current_longitude")

        alert = SOSAlert.objects.create(
            user=request.user,
            neighborhood=_resolve_neighborhood(request.user, lat, lon),
            status=SOSAlert.Status.ACTIVE,
            started_at=timezone.now(),
            current_latitude=lat,
            current_longitude=lon,
            address=request.data.get("address", ""),
            metadata=request.data.get("metadata", {}),
        )

        from apps.notifications.services import NotificationDispatchService
        NotificationDispatchService.dispatch_sos_alert(alert)

        return Response(SOSAlertSerializer(alert).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _stop_sirens(alert):
        from apps.notifications.services import NotificationDispatchService

        NotificationDispatchService.broadcast_sos_ended(alert)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """List active SOS alerts (coordinator/police/admin only).

        System admins see all active alerts.
        Coordinators and police see only alerts in their own neighborhoods.
        """
        user = request.user
        if not user.role_id or user.role.code not in (
            Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN, Role.Code.POLICE_OFFICER
        ):
            raise PermissionDenied("Only coordinators, police, or administrators can view active alerts.")

        if user.role.code == Role.Code.SYSTEM_ADMIN:
            alerts = SOSAlert.objects.filter(status=SOSAlert.Status.ACTIVE).order_by("-created_at")
        else:
            # Scope to neighborhoods where this user has membership to prevent
            # cross-neighborhood information leakage.
            user_neighborhoods = user.neighborhood_memberships.values_list(
                "neighborhood_id", flat=True
            )
            alerts = SOSAlert.objects.filter(
                status=SOSAlert.Status.ACTIVE,
                neighborhood_id__in=user_neighborhoods,
            ).order_by("-created_at")

        return Response(SOSAlertSerializer(alerts, many=True).data)

    @action(detail=True, methods=["post"])
    def ping(self, request, pk=None):
        """Add a location ping to an active SOS alert."""
        alert = self.get_object()
        if alert.user_id != request.user.pk:
            raise PermissionDenied("You can only ping your own SOS alert.")
        if alert.status not in (SOSAlert.Status.ACTIVE, SOSAlert.Status.ESCALATED):
            raise ValidationError({"detail": "Cannot ping a resolved or cancelled alert."})

        if "captured_at" not in request.data:
            raise ValidationError({"captured_at": "This field is required."})
        lat, lon = _parse_coordinates(request.data, "latitude", "longitude")

        ping = SOSLocationPing.objects.create(
            sos_alert=alert,
            latitude=lat,
            longitude=lon,
            accuracy_m=request.data.get("accuracy_m"),
            captured_at=request.data["captured_at"],
        )
        alert.current_latitude = lat
        alert.current_longitude = lon
        alert.save(update_fields=["current_latitude", "current_longitude", "updated_at", "last_modified_at"])

        return Response(SOSLocationPingSerializer(ping).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Mark an SOS alert as resolved."""
        alert = self.get_object()
        if alert.user_id != request.user.pk:
            raise PermissionDenied("You can only resolve your own SOS alert.")
        if alert.status in (SOSAlert.Status.RESOLVED, SOSAlert.Status.CANCELLED):
            raise ValidationError({"detail": "Alert is already closed."})
        alert.status = SOSAlert.Status.RESOLVED
        alert.ended_at = timezone.now()
        alert.save(update_fields=["status", "ended_at", "updated_at", "last_modified_at"])
        self._stop_sirens(alert)
        return Response(SOSAlertSerializer(alert).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel an SOS alert."""
        alert = self.get_object()
        if alert.user_id != request.user.pk:
            raise PermissionDenied("You can only cancel your own SOS alert.")
        if alert.status in (SOSAlert.Status.RESOLVED, SOSAlert.Status.CANCELLED):
            raise ValidationError({"detail": "Alert is already closed."})
        alert.status = SOSAlert.Status.CANCELLED
        alert.ended_at = timezone.now()
        alert.save(update_fields=["status", "ended_at", "updated_at", "last_modified_at"])
        self._stop_sirens(alert)
        return Response(SOSAlertSerializer(alert).data)
