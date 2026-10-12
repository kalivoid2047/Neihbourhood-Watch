from django.core.management.base import BaseCommand

from apps.accounts.models import Permission, Role


ROLE_PERMISSIONS = {
    Role.Code.RESIDENT: [
        "incidents.create",
        "incidents.view_own",
        "alerts.view",
        "sos.create",
        "sync.use",
    ],
    Role.Code.BLOCK_CAPTAIN: [
        "incidents.create",
        "incidents.view_neighborhood",
        "incidents.verify",
        "alerts.send_neighborhood",
        "sos.monitor_neighborhood",
        "users.recommend_verification",
        "sync.use",
    ],
    Role.Code.COORDINATOR: [
        "users.verify",
        "incidents.manage_neighborhood",
        "alerts.send_neighborhood",
        "sos.monitor_neighborhood",
        "analytics.view_neighborhood",
        "audit.view_neighborhood",
    ],
    Role.Code.POLICE_OFFICER: [
        "incidents.view_critical",
        "incidents.view_evidence",
        "sos.monitor_active",
        "analytics.view_operational",
    ],
    Role.Code.SYSTEM_ADMIN: [
        "admin.manage_system",
        "users.manage",
        "roles.manage",
        "incidents.manage_all",
        "analytics.view_all",
        "audit.view_all",
        "settings.manage",
    ],
}

PERMISSION_NAMES = {
    "admin.manage_system": "Manage system administration",
    "users.manage": "Manage users",
    "users.verify": "Verify residents",
    "users.recommend_verification": "Recommend resident verification",
    "roles.manage": "Manage roles and permissions",
    "incidents.create": "Create incident reports",
    "incidents.view_own": "View own incidents",
    "incidents.view_neighborhood": "View neighborhood incidents",
    "incidents.view_critical": "View critical incidents",
    "incidents.view_evidence": "View incident evidence",
    "incidents.verify": "Verify incidents",
    "incidents.manage_neighborhood": "Manage neighborhood incidents",
    "incidents.manage_all": "Manage all incidents",
    "alerts.view": "View alerts",
    "alerts.send_neighborhood": "Send neighborhood alerts",
    "sos.create": "Create SOS sessions",
    "sos.monitor_neighborhood": "Monitor neighborhood SOS sessions",
    "sos.monitor_active": "Monitor active SOS sessions",
    "analytics.view_neighborhood": "View neighborhood analytics",
    "analytics.view_operational": "View operational analytics",
    "analytics.view_all": "View all analytics",
    "audit.view_neighborhood": "View neighborhood audit logs",
    "audit.view_all": "View all audit logs",
    "settings.manage": "Manage settings",
    "sync.use": "Use offline synchronization",
}


class Command(BaseCommand):
    help = "Seed baseline NHWZ roles and permissions."

    def handle(self, *args, **options):
        permissions = {}
        for code, name in PERMISSION_NAMES.items():
            permission, _ = Permission.objects.update_or_create(
                code=code,
                defaults={"name": name},
            )
            permissions[code] = permission

        for role_code, permission_codes in ROLE_PERMISSIONS.items():
            role, _ = Role.objects.update_or_create(
                code=role_code,
                defaults={
                    "name": Role.Code(role_code).label,
                    "is_system": True,
                },
            )
            role.permissions.set([permissions[code] for code in permission_codes])

        self.stdout.write(self.style.SUCCESS("Seeded NHWZ roles and permissions."))

