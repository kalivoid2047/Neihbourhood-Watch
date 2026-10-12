from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

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


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "phone_number",
        "role",
        "verification_status",
        "is_active",
        "is_staff",
    )
    list_filter = ("verification_status", "role", "is_active", "is_staff")
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

