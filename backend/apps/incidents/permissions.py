from django.conf import settings
from django.db.models import Q
from rest_framework.permissions import BasePermission

from apps.accounts.models import Role
from apps.core.geo import box_q, in_box


def nearby_visibility_q(user) -> Q | None:
    """Q for incidents close to where *user* is now, or ``None`` if unknown.

    Uses a bounding box (not a true circle) so this and the Python check in
    :func:`user_can_view_incident` agree exactly: an incident that shows up in
    someone's list can always be opened.
    """
    location = user.effective_location()
    if location is None:
        return None
    radius = getattr(settings, "INCIDENT_NEARBY_VISIBILITY_RADIUS_M", 5000)
    return box_q("latitude", "longitude", location[0], location[1], radius)


class IsIncidentReporter(BasePermission):
    """Allows incident reporter to update their own incident."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.reporter_id == request.user.id


def user_can_view_incident(user, incident) -> bool:
    """Single source of truth for "may this user see this incident?".

    Used by the REST permission below *and* the incident WebSocket consumer, so
    live updates can never leak an incident the API would refuse to show.

    - System admins: everything.
    - Reporter and assignee: their own / assigned incidents.
    - Residents, block captains, coordinators and police: incidents in a
      neighborhood they belong to, or reported close to where they are right
      now (this matches the list queryset, so an incident that appears in a
      user's list can always be opened).
    """
    if not user or not user.is_authenticated or not user.role_id:
        return False

    role_code = user.role.code

    if role_code == Role.Code.SYSTEM_ADMIN:
        return True
    if incident.reporter_id == user.id or incident.assigned_to_id == user.id:
        return True

    if role_code in (
        Role.Code.RESIDENT,
        Role.Code.BLOCK_CAPTAIN,
        Role.Code.COORDINATOR,
        Role.Code.POLICE_OFFICER,
    ):
        if incident.neighborhood_id and user.neighborhood_memberships.filter(
            neighborhood_id=incident.neighborhood_id
        ).exists():
            return True
        location = user.effective_location()
        if location is not None:
            radius = getattr(settings, "INCIDENT_NEARBY_VISIBILITY_RADIUS_M", 5000)
            return in_box(incident.latitude, incident.longitude, location[0], location[1], radius)

    return False


class CanViewIncident(BasePermission):
    """Object-level wrapper around :func:`user_can_view_incident`."""

    def has_object_permission(self, request, view, obj):
        return user_can_view_incident(request.user, obj)


class CanVerifyIncident(BasePermission):
    """Only coordinators and admins can verify incidents."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.role_id:
            return False

        role_code = request.user.role.code
        return role_code in (Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN)


class CanAssignIncident(BasePermission):
    """Only coordinators and admins can assign incidents."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.role_id:
            return False

        role_code = request.user.role.code
        return role_code in (Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN)


class CanUploadIncidentMedia(BasePermission):
    """
    - Incident reporter can upload media
    - Police/coordinators in neighborhood can upload media
    - Admins can upload media

    ``obj`` is the Incident instance — passed directly from the upload_media action.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.role_id:
            return False

        user = request.user
        role_code = user.role.code
        # obj is the incident — no secondary get_object() call needed.
        incident = obj

        if role_code == Role.Code.SYSTEM_ADMIN:
            return True

        if incident.reporter_id == user.id:
            return True

        if incident.assigned_to_id == user.id:
            return True

        if role_code in (
            Role.Code.BLOCK_CAPTAIN,
            Role.Code.COORDINATOR,
            Role.Code.POLICE_OFFICER,
        ):
            if incident.neighborhood_id:
                return user.neighborhood_memberships.filter(
                    neighborhood_id=incident.neighborhood_id,
                ).exists()

        return False
