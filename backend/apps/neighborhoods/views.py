"""Views for the neighborhoods app."""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.incidents.services import IncidentGeospatialService

from .models import Neighborhood, NeighborhoodMembership
from .permissions import IsCoordinatorOrAdmin, IsSystemAdmin
from .serializers import (
    NeighborhoodCreateSerializer,
    NeighborhoodMemberRoleSerializer,
    NeighborhoodMemberSerializer,
    NeighborhoodRiskSummarySerializer,
    NeighborhoodSerializer,
)


class NeighborhoodViewSet(viewsets.ModelViewSet):
    """
    Neighborhood CRUD with membership management.

    - GET list/detail: public (no authentication required)
    - POST create: system admin only
    - PATCH update: system admin only
    - DELETE: not exposed
    - join: any authenticated user
    - leave: authenticated user (removes own membership)
    - members: coordinator or system admin
    - member_role: coordinator or system admin
    - risk_summary: any authenticated user
    """

    queryset = Neighborhood.objects.filter(is_active=True).order_by("name")
    serializer_class = NeighborhoodSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        # list/retrieve are public; write actions require specific roles.
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        if self.action in ("create", "partial_update", "destroy"):
            return [IsAuthenticated(), IsSystemAdmin()]
        if self.action in ("members", "member_role"):
            return [IsAuthenticated(), IsCoordinatorOrAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return NeighborhoodCreateSerializer
        return NeighborhoodSerializer

    # ── Standard CRUD (gated) ─────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        serializer = NeighborhoodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        neighborhood = serializer.save()
        return Response(NeighborhoodSerializer(neighborhood).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        neighborhood = self.get_object()
        neighborhood.is_active = False
        neighborhood.save(update_fields=["is_active", "updated_at", "last_modified_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Membership actions ────────────────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """Join a neighborhood. Automatically set as primary if the user has no primary."""
        neighborhood = self.get_object()
        user = request.user
        if NeighborhoodMembership.objects.filter(
            user=user, neighborhood=neighborhood, deleted_at__isnull=True
        ).exists():
            raise ValidationError({"detail": "You are already a member of this neighborhood."})
        is_primary = not NeighborhoodMembership.objects.filter(
            user=user, is_primary=True, deleted_at__isnull=True
        ).exists()
        membership = NeighborhoodMembership.objects.create(
            user=user,
            neighborhood=neighborhood,
            role=NeighborhoodMembership.Role.RESIDENT,
            is_primary=is_primary,
        )
        return Response(NeighborhoodMemberSerializer(membership).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"])
    def leave(self, request, pk=None):
        """Leave a neighborhood (soft-delete the membership)."""
        neighborhood = self.get_object()
        membership = NeighborhoodMembership.objects.filter(
            user=request.user, neighborhood=neighborhood, deleted_at__isnull=True
        ).first()
        if not membership:
            raise ValidationError({"detail": "You are not a member of this neighborhood."})
        membership.deleted_at = timezone.now()
        membership.is_primary = False
        membership.save(update_fields=["deleted_at", "is_primary", "updated_at", "last_modified_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """List members of a neighborhood (coordinator/admin only)."""
        neighborhood = self.get_object()
        memberships = (
            NeighborhoodMembership.objects.filter(
                neighborhood=neighborhood, deleted_at__isnull=True
            )
            .select_related("user")
            .order_by("role", "user__full_name")
        )
        return Response(NeighborhoodMemberSerializer(memberships, many=True).data)

    @action(detail=True, methods=["post"], url_path=r"members/(?P<user_id>[^/.]+)/role")
    def member_role(self, request, pk=None, user_id=None):
        """Change a member's role within a neighborhood (coordinator/admin only)."""
        neighborhood = self.get_object()
        membership = NeighborhoodMembership.objects.filter(
            neighborhood=neighborhood, user_id=user_id, deleted_at__isnull=True
        ).first()
        if not membership:
            raise ValidationError({"detail": "No active membership found for this user."})
        serializer = NeighborhoodMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership.role = serializer.validated_data["role"]
        membership.save(update_fields=["role", "updated_at", "last_modified_at"])
        return Response(NeighborhoodMemberSerializer(membership).data)

    @action(detail=True, methods=["get"])
    def risk_summary(self, request, pk=None):
        """Return incident risk metrics for a neighborhood."""
        neighborhood = self.get_object()
        try:
            days = int(request.query_params.get("days", 30))
        except (ValueError, TypeError):
            raise ValidationError({"days": "Must be a positive integer."})
        if days < 1:
            raise ValidationError({"days": "Must be at least 1."})
        summary = IncidentGeospatialService.neighborhood_risk_summary(neighborhood.pk, days=days)
        return Response(NeighborhoodRiskSummarySerializer(summary).data)
