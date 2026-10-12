from django.contrib import admin

from .models import Incident, IncidentMedia


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "severity", "status", "reporter", "occurred_at")
    list_filter = ("category", "severity", "status")
    search_fields = ("title", "description", "address", "reporter__email")
    autocomplete_fields = ("reporter", "neighborhood", "verified_by", "assigned_to")


@admin.register(IncidentMedia)
class IncidentMediaAdmin(admin.ModelAdmin):
    list_display = ("incident", "media_type", "mime_type", "size_bytes", "uploaded_at")
    list_filter = ("media_type",)
    search_fields = ("incident__title", "original_filename", "checksum")
    autocomplete_fields = ("incident", "uploaded_by")

