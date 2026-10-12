from rest_framework.permissions import BasePermission


class HasRoleCapability(BasePermission):
    """Checks custom role permissions declared on a DRF view."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        required = set(getattr(view, "required_permissions", ()))
        if not required:
            return True
        if not request.user.role_id:
            return False

        granted = set(
            request.user.role.permissions.filter(code__in=required).values_list(
                "code",
                flat=True,
            )
        )
        return required.issubset(granted)


class HasAnyRole(BasePermission):
    """Allows access to users with one of the view's required role codes."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        required_role_codes = set(getattr(view, "required_role_codes", ()))
        if not required_role_codes:
            return True
        if not request.user.role_id:
            return False

        return request.user.role.code in required_role_codes
