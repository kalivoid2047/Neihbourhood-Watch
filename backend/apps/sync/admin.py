from django.contrib import admin

from .models import SyncQueue


@admin.register(SyncQueue)
class SyncQueueAdmin(admin.ModelAdmin):
    list_display = ("user", "entity_type", "operation", "status", "retry_count", "local_modified_at")
    list_filter = ("operation", "status", "entity_type")
    search_fields = ("user__email", "entity_type", "entity_id", "idempotency_key")
    autocomplete_fields = ("user",)

