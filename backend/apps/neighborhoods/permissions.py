"""DRF permission classes for the neighborhoods app."""

from rest_framework.permissions import BasePermission

from apps.accounts.models import Role


class IsSystemAdmin(BasePermission):
    """Allows access only to users with the system_admin role."""

    message = "Only system administrators can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role_id
            and request.user.role.code == Role.Code.SYSTEM_ADMIN
        )


class IsCoordinatorOrAdmin(BasePermission):
    """Allows access to coordinators and system admins."""

    message = "Only coordinators or administrators can perform this action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.role_id):
            return False
        return request.user.role.code in (Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN)
