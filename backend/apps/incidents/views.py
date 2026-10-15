import hashlib
import logging

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Role, User
from apps.audit.services import create_audit_log, snapshot_model
from apps.core.broadcasting import broadcast_incident_update
from apps.notifications.services import NotificationDispatchService

from .filters import IncidentFilterSet
from .models import Incident, IncidentMedia
from .permissions import (
    CanAssignIncident,
    CanUploadIncidentMedia,
    CanVerifyIncident,
    CanViewIncident,
    IsIncidentReporter,
    nearby_visibility_q,
    user_can_view_incident,
)
from .serializers import (
    HeatmapCellSerializer,
    IncidentAssignmentSerializer,
    IncidentCreateSerializer,
    IncidentListSerializer,
    IncidentMediaListSerializer,
    IncidentMediaSerializer,
    IncidentMediaUploadSerializer,
    IncidentSerializer,
    IncidentStatusTransitionSerializer,
    IncidentUpdateSerializer,
    NearbyIncidentSerializer,
)
from .services import IncidentGeospatialService, IncidentStatusTransitionService


logger = logging.getLogger(__name__)


def _compute_sha256(file_obj) -> str:
    """Return the hex-encoded SHA-256 digest of an uploaded file object."""
    sha = hashlib.sha256()
    file_obj.seek(0)
    for chunk in file_obj.chunks():
        sha.update(chunk)
    file_obj.seek(0)
    return sha.hexdigest()


class IncidentViewSet(viewsets.ModelViewSet):
    """
    Incident CRUD with role-based filtering and status transitions.

    - Residents see own incidents and neighborhood incidents.
    - Block captains see neighborhood incidents.
    - Coordinators see neighborhood incidents and can verify/assign.
    - Police see assigned incidents and neighborhood incidents.
    - Admins see all incidents.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # Without these the clients' filter and search controls are accepted and
    # then silently ignored, which looks to a user like "the filter is broken"
    # but reads in the logs like a perfectly normal request.
    filterset_class = IncidentFilterSet
    search_fields = ["title", "description", "address"]
    ordering_fields = ["occurred_at", "created_at", "severity", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return IncidentCreateSerializer
        if self.action == "partial_update":
            return IncidentUpdateSerializer
        if self.action == "list":
            return IncidentListSerializer
        return IncidentSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.role_id:
            # No role yet: still show the incidents this account reported or was assigned.
            return Incident.objects.filter(Q(reporter_id=user.id) | Q(assigned_to_id=user.id)).select_related(
                "reporter", "neighborhood", "verified_by", "assigned_to"
            ).order_by("-created_at")

        role_code = user.role.code

        # System admin sees all
        if role_code == Role.Code.SYSTEM_ADMIN:
            return Incident.objects.select_related(
                "reporter",
                "neighborhood",
                "verified_by",
                "assigned_to",
            )

        # Build query based on role
        q = Q()

        # Everyone sees their own reported incidents
        q |= Q(reporter_id=user.id)

        # Everyone sees incidents assigned to them
        q |= Q(assigned_to_id=user.id)

        # All non-admin roles see incidents from their own neighborhoods.
        # The same membership query applies to every role; no per-role branching needed.
        if role_code in (
            Role.Code.RESIDENT,
            Role.Code.BLOCK_CAPTAIN,
            Role.Code.COORDINATOR,
            Role.Code.POLICE_OFFICER,
        ):
            user_neighborhoods = user.neighborhood_memberships.values_list(
                "neighborhood_id",
                flat=True,
            )
            q |= Q(neighborhood_id__in=user_neighborhoods)

            # ...and anything reported close to where they are right now, even
            # in a neighbourhood they have not joined.
            nearby_q = nearby_visibility_q(user)
            if nearby_q is not None:
                q |= nearby_q

        return (
            Incident.objects.filter(q)
            .select_related(
                "reporter",
                "neighborhood",
                "verified_by",
                "assigned_to",
            )
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        incident = serializer.save()
        create_audit_log(
            action="incident_created",
            actor=self.request.user,
            entity=incident,
            request=self.request,
            after=snapshot_model(incident),
        )
        self._maybe_alert_on_create(incident)
        self._push_to_nearby_maps(incident)

    @staticmethod
    def _push_to_nearby_maps(incident):
        """Drop the new incident onto the live map of everyone close by."""
        try:
            NotificationDispatchService.broadcast_incident_to_nearby(incident)
        except Exception:
            logger.exception("Failed to push incident %s to nearby maps", incident.pk)

    @staticmethod
    def _maybe_alert_on_create(incident):
        """Alert neighbours immediately for the most severe reports.

        Normally alerts wait for a coordinator to verify an incident, which
        keeps false alarms down.  That trade-off is wrong for a life-safety
        report: waiting minutes for verification defeats the purpose of an
        alarm.  So the severities listed in ``INCIDENT_ALERT_ON_CREATE_SEVERITIES``
        alert on creation, and the mobile app badges them "not verified yet".

        Set ``INCIDENT_ALERT_ON_CREATE_SEVERITIES = []`` to require
        verification for everything.
        """
        from django.conf import settings

        severities = getattr(settings, "INCIDENT_ALERT_ON_CREATE_SEVERITIES", ["red"])
        if incident.severity not in severities:
            return

        try:
            NotificationDispatchService.dispatch_incident_alert(incident)
        except Exception:
            # A failed fan-out must never lose the report itself — the incident
            # is already saved, and the mobile clients will pick it up on their
            # next poll regardless.
            logger.exception("Failed to dispatch create-time alert for incident %s", incident.pk)

    def perform_update(self, serializer):
        before = snapshot_model(
            serializer.instance,
            fields=["title", "description", "category", "severity", "address"],
        )
        incident = serializer.save()
        Incident.objects.filter(pk=incident.pk).update(sync_version=F("sync_version") + 1)
        incident.refresh_from_db(fields=["sync_version"])
        create_audit_log(
            action="incident_updated",
            actor=self.request.user,
            entity=incident,
            request=self.request,
            before=before,
            after=snapshot_model(
                incident,
                fields=["title", "description", "category", "severity", "address"],
            ),
        )
        broadcast_incident_update(incident)

    def get_object(self):
        obj = super().get_object()
        # Check view permission
        permission = CanViewIncident()
        if not permission.has_object_permission(self.request, self, obj):
            self.permission_denied(self.request)
        return obj

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanVerifyIncident])
    def verify(self, request, pk=None):
        """Verify an incident."""
        incident = self.get_object()
        serializer = IncidentStatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["new_status"]
        if new_status != Incident.Status.VERIFIED:
            raise ValidationError({"new_status": "Only 'verified' status is allowed in this action."})

        if not IncidentStatusTransitionService.can_transition(incident.status, new_status):
            raise ValidationError(
                {
                    "detail": f"Cannot transition from {incident.Status(incident.status).label} to {Incident.Status(new_status).label}."
                }
            )

        IncidentStatusTransitionService.transition(
            incident,
            new_status,
            actor=request.user,
            request=request,
        )
        broadcast_incident_update(incident)
        return Response(IncidentSerializer(incident).data)

    @action(detail=True, methods=["post"])
    def transition_status(self, request, pk=None):
        """Transition incident status through workflow."""
        incident = self.get_object()

        # Only coordinators and admins can transition status
        if not request.user.role_id or request.user.role.code not in (
            Role.Code.COORDINATOR,
            Role.Code.SYSTEM_ADMIN,
        ):
            self.permission_denied(request)

        serializer = IncidentStatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["new_status"]
        if not IncidentStatusTransitionService.can_transition(incident.status, new_status):
            raise ValidationError(
                {
                    "detail": f"Cannot transition from {incident.Status(incident.status).label} to {Incident.Status(new_status).label}."
                }
            )

        IncidentStatusTransitionService.transition(
            incident,
            new_status,
            actor=request.user,
            request=request,
        )
        broadcast_incident_update(incident)
        return Response(IncidentSerializer(incident).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanAssignIncident])
    def assign(self, request, pk=None):
        """Assign incident to a user."""
        incident = self.get_object()
        serializer = IncidentAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assigned_to_id = serializer.validated_data.get("assigned_to_id")
        assigned_to = None
        if assigned_to_id:
            assigned_to = User.objects.get(id=assigned_to_id)

        IncidentStatusTransitionService.assign(
            incident,
            assigned_to,
            actor=request.user,
            request=request,
        )
        broadcast_incident_update(incident)
        return Response(IncidentSerializer(incident).data)

    @action(detail=True, methods=["get"])
    def media(self, request, pk=None):
        """List media for incident."""
        incident = self.get_object()
        media_qs = incident.media.filter(deleted_at__isnull=True)
        serializer = IncidentMediaListSerializer(media_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload_media(self, request, pk=None):
        """Upload media to incident."""
        incident = self.get_object()

        # Check upload permission
        permission = CanUploadIncidentMedia()
        if not permission.has_object_permission(request, self, incident):
            self.permission_denied(request)

        serializer = IncidentMediaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data["file"]
        media_type = serializer.validated_data["media_type"]
        metadata = serializer.validated_data.get("metadata", {})

        checksum = _compute_sha256(file_obj)

        # Create media record
        media = IncidentMedia.objects.create(
            incident=incident,
            uploaded_by=request.user,
            media_type=media_type,
            file=file_obj,
            original_filename=file_obj.name,
            mime_type=file_obj.content_type or "application/octet-stream",
            size_bytes=file_obj.size,
            checksum=checksum,
            metadata=metadata,
        )

        create_audit_log(
            action="incident_media_uploaded",
            actor=request.user,
            entity=media,
            request=request,
            after=snapshot_model(media),
        )
        broadcast_incident_update(incident)

        return Response(IncidentMediaSerializer(media).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def nearby(self, request):
        """Return incidents within a radius of a geographic coordinate.

        Query parameters:
            latitude (float, required): Reference latitude.
            longitude (float, required): Reference longitude.
            radius_m (float, optional): Search radius in metres (default 5000, max 50000).
            status (str, repeatable): Filter by one or more incident statuses.
        """
        try:
            lat = float(request.query_params["latitude"])
            lon = float(request.query_params["longitude"])
        except (KeyError, ValueError):
            raise ValidationError({"detail": "latitude and longitude query parameters are required."})

        try:
            radius_m = float(request.query_params.get("radius_m", 5000))
        except ValueError:
            raise ValidationError({"radius_m": "Must be a number."})

        if not (-90 <= lat <= 90):
            raise ValidationError({"latitude": "Must be between -90 and 90."})
        if not (-180 <= lon <= 180):
            raise ValidationError({"longitude": "Must be between -180 and 180."})
        if not (1 <= radius_m <= 50_000):
            raise ValidationError({"radius_m": "Must be between 1 and 50000 metres."})

        statuses = request.query_params.getlist("status") or None
        base_qs = self.get_queryset()
        results = IncidentGeospatialService.nearby_incidents(lat, lon, radius_m, base_qs, statuses)

        # Anything reported close to the point being asked about is visible to
        # any signed-in resident, whether or not they joined its neighbourhood
        # (capped at the nearby-visibility radius so this cannot be used to
        # scrape the whole city).
        if request.user.role_id and request.user.role.code != Role.Code.SYSTEM_ADMIN:
            cap = getattr(settings, "INCIDENT_NEARBY_VISIBILITY_RADIUS_M", 5000)
            seen = {incident.pk for _, incident in results}
            extra = IncidentGeospatialService.nearby_incidents(
                lat, lon, min(radius_m, cap), Incident.objects.all(), statuses
            )
            results = sorted(
                results + [pair for pair in extra if pair[1].pk not in seen],
                key=lambda pair: pair[0],
            )

        incidents = []
        for dist, incident in results:
            incident._distance_m = dist
            incidents.append(incident)

        serializer = NearbyIncidentSerializer(incidents, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def heatmap(self, request):
        """Return an incident heatmap grid for a neighborhood or bounding box.

        Query parameters (one of the following is required):
            neighborhood_id (UUID): Filter to a specific neighborhood.
            bounds (str): Comma-separated ``min_lat,min_lon,max_lat,max_lon``.
        Optional:
            days (int): Look-back window in days (default 7).
        """
        neighborhood_id = request.query_params.get("neighborhood_id")
        bounds_raw = request.query_params.get("bounds")
        days_raw = request.query_params.get("days", 7)

        try:
            days = int(days_raw)
        except (ValueError, TypeError):
            raise ValidationError({"days": "Must be a positive integer."})
        if days < 1:
            raise ValidationError({"days": "Must be at least 1."})

        bounds = None
        if bounds_raw:
            try:
                parts = [float(v) for v in bounds_raw.split(",")]
                if len(parts) != 4:
                    raise ValueError
                min_lat, min_lon, max_lat, max_lon = parts
                if min_lat >= max_lat or min_lon >= max_lon:
                    raise ValueError
                bounds = (min_lat, min_lon, max_lat, max_lon)
            except ValueError:
                raise ValidationError({"bounds": "Must be min_lat,min_lon,max_lat,max_lon."})

        if not neighborhood_id and not bounds:
            raise ValidationError({"detail": "Either neighborhood_id or bounds is required."})

        cells = IncidentGeospatialService.incident_heatmap(
            neighborhood_id=neighborhood_id,
            bounds=bounds,
            days=days,
        )
        serializer = HeatmapCellSerializer(cells, many=True)
        return Response(serializer.data)


class IncidentMediaDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete incident media."""

    queryset = IncidentMedia.objects.filter(deleted_at__isnull=True)
    serializer_class = IncidentMediaSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        media = super().get_object()
        # Same visibility rule as the incident itself; hide existence otherwise.
        if not user_can_view_incident(self.request.user, media.incident):
            raise NotFound()
        return media

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.role_id:
            raise PermissionDenied("You do not have permission to delete this media.")

        role_code = user.role.code
        is_uploader = instance.uploaded_by_id == user.id
        is_admin = role_code == Role.Code.SYSTEM_ADMIN
        # Coordinators may delete media from incidents in their neighborhoods
        is_coordinator_in_neighborhood = (
            role_code in (Role.Code.COORDINATOR, Role.Code.POLICE_OFFICER)
            and instance.incident.neighborhood_id
            and user.neighborhood_memberships.filter(
                neighborhood_id=instance.incident.neighborhood_id,
            ).exists()
        )
        if not (is_uploader or is_admin or is_coordinator_in_neighborhood):
            raise PermissionDenied("Only the uploader or a coordinator in this neighborhood can delete media.")

        before = snapshot_model(instance)
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at", "last_modified_at"])

        create_audit_log(
            action="incident_media_deleted",
            actor=self.request.user,
            entity=instance,
            request=self.request,
            before=before,
        )
        broadcast_incident_update(instance.incident)
