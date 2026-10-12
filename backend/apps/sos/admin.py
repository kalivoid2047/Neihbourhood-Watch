from django.contrib import admin

from .models import SOSAlert, SOSLocationPing


@admin.register(SOSAlert)
class SOSAlertAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "neighborhood", "started_at", "ended_at")
    list_filter = ("status",)
    search_fields = ("user__email", "address")
    autocomplete_fields = ("user", "neighborhood")


@admin.register(SOSLocationPing)
class SOSLocationPingAdmin(admin.ModelAdmin):
    list_display = ("sos_alert", "latitude", "longitude", "captured_at")
    search_fields = ("sos_alert__user__email",)
    autocomplete_fields = ("sos_alert",)

