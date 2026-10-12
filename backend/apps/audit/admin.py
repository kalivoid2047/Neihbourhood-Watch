from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "action", "entity_type", "entity_id", "created_at")
    list_filter = ("action", "entity_type")
    search_fields = ("actor__email", "action", "entity_type", "entity_id")
    autocomplete_fields = ("actor",)
    readonly_fields = ("created_at", "updated_at", "last_modified_at")

