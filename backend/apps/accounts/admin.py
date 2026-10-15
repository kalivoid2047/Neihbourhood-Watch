from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.neighborhoods.models import NeighborhoodMembership

from .models import (
    DeviceToken,
    EmergencyContact,
    OTPChallenge,
    Permission,
    Role,
    RolePermission,
    User,
    VerificationRequest,
)


class NeighborhoodMembershipInline(admin.TabularInline):
    model = NeighborhoodMembership
    extra = 0
    fields = ("neighborhood", "role", "is_primary")
    autocomplete_fields = ("neighborhood",)
    verbose_name = "neighbourhood membership"


def _set_role_action(role_code):
    label = Role.Code(role_code).label

    @admin.action(description=f"Set role: {label}")
    def action(modeladmin, request, queryset):
        role, _ = Role.objects.get_or_create(
            code=role_code, defaults={"name": label, "is_system": True}
        )
        n = 0
        for user in queryset:
            user.role = role
            user.block_captain_applied_at = None
            _sync_admin_access(user)
            user.save()
            n += 1
        modeladmin.message_user(request, f"{n} account(s) set to {label}.", messages.SUCCESS)

    action.__name__ = f"set_role_{role_code}"
    return action


def _sync_admin_access(user):
    """System administrators can sign in to this admin site."""
    if user.role and user.role.code == Role.Code.SYSTEM_ADMIN:
        user.is_staff = True
        user.is_superuser = True


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = (NeighborhoodMembershipInline,)
    date_hierarchy = "date_joined"
    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "phone_number",
        "role",
        "applied_for_block_captain",
        "verification_status",
        "is_active",
        "is_staff",
    )
    list_filter = ("role", "block_captain_applied_at", "verification_status", "is_active", "is_staff")
    actions = (
        "approve_block_captain",
        "decline_block_captain",
        "mark_verified",
        "activate_accounts",
        "deactivate_accounts",
    )

    def get_actions(self, request):
        actions = super().get_actions(request)
        for code in Role.Code.values:
            fn = _set_role_action(code)
            actions[fn.__name__] = (fn, fn.__name__, fn.short_description)
        return actions

    @admin.action(description="Mark as verified (approved)")
    def mark_verified(self, request, queryset):
        n = queryset.update(
            verification_status=User.VerificationStatus.APPROVED,
            otp_verified_at=timezone.now(),
        )
        self.message_user(request, f"{n} account(s) verified.", messages.SUCCESS)

    @admin.action(description="Activate accounts")
    def activate_accounts(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_active=True)} account(s) activated.", messages.SUCCESS)

    @admin.action(description="Deactivate accounts (block sign-in)")
    def deactivate_accounts(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)
        self.message_user(request, f"{queryset.update(is_active=False)} account(s) deactivated.", messages.WARNING)

    def save_model(self, request, obj, form, change):
        if not change:
            # Accounts an admin creates are trusted: no OTP step needed.
            if obj.verification_status == User.VerificationStatus.RESIDENT:
                obj.verification_status = User.VerificationStatus.APPROVED
            obj.otp_verified_at = obj.otp_verified_at or timezone.now()
        _sync_admin_access(obj)
        super().save_model(request, obj, form, change)

    @admin.display(boolean=True, description="Applied: block captain", ordering="block_captain_applied_at")
    def applied_for_block_captain(self, obj):
        return obj.block_captain_applied_at is not None

    @admin.action(description="Approve block captain application(s)")
    def approve_block_captain(self, request, queryset):
        role, _ = Role.objects.get_or_create(
            code=Role.Code.BLOCK_CAPTAIN,
            defaults={"name": Role.Code.BLOCK_CAPTAIN.label, "is_system": True},
        )
        n = 0
        for user in queryset.filter(block_captain_applied_at__isnull=False):
            user.role = role
            user.block_captain_applied_at = None
            user.save()
            n += 1
        self.message_user(request, f"{n} account(s) are now block captains.")

    @admin.action(description="Decline block captain application(s)")
    def decline_block_captain(self, request, queryset):
        n = queryset.filter(block_captain_applied_at__isnull=False).update(block_captain_applied_at=None)
        self.message_user(request, f"{n} application(s) declined.")
    search_fields = ("email", "full_name", "phone_number", "national_id")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "full_name",
                    "phone_number",
                    "national_id",
                    "address",
                    "latitude",
                    "longitude",
                    "profile_photo",
                )
            },
        ),
        (
            _("Access"),
            {
                "fields": (
                    "role",
                    "block_captain_applied_at",
                    "verification_status",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "phone_number",
                    "national_id",
                    "address",
                    "role",
                    "verification_status",
                    "is_active",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_system", "created_at")
    search_fields = ("code", "name")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "created_at")
    search_fields = ("code", "name")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "created_at")
    autocomplete_fields = ("role", "permission")


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "reviewed_by", "reviewed_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "user__full_name", "notes")
    autocomplete_fields = ("user", "reviewed_by")


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "is_active", "last_seen_at", "created_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__email", "token")
    autocomplete_fields = ("user",)


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "phone_number", "relationship", "priority")
    search_fields = ("user__email", "name", "phone_number")
    autocomplete_fields = ("user",)


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "channel", "expires_at", "consumed_at", "created_at")
    list_filter = ("purpose", "channel")
    autocomplete_fields = ("user",)

