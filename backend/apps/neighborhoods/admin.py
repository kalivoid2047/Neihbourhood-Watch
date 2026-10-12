from django.contrib import admin

from .models import Neighborhood, NeighborhoodMembership


@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "province", "alert_radius_m", "is_active")
    list_filter = ("province", "city", "is_active")
    search_fields = ("name", "code", "city", "province")


@admin.register(NeighborhoodMembership)
class NeighborhoodMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "neighborhood", "role", "is_primary", "created_at")
    list_filter = ("role", "is_primary")
    search_fields = ("user__email", "neighborhood__name")
    autocomplete_fields = ("user", "neighborhood")

