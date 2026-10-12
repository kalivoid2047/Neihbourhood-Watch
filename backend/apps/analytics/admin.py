from django.contrib import admin

from .models import AnalyticsSnapshot


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ("snapshot_type", "neighborhood", "period_start", "period_end", "generated_at")
    list_filter = ("snapshot_type",)
    search_fields = ("snapshot_type", "neighborhood__name")
    autocomplete_fields = ("neighborhood", "generated_by")

