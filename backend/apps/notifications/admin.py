from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "channel", "status", "priority", "title", "created_at")
    list_filter = ("channel", "status", "priority")
    search_fields = ("recipient__email", "title", "body")
    autocomplete_fields = ("recipient", "incident", "sos_alert")

