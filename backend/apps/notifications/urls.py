from django.urls import path

from .views import (
    NotificationDeleteView,
    NotificationPreferenceView,
    NotificationReadView,
    UserNotificationListView,
)

urlpatterns = [
    path("me/notifications/", UserNotificationListView.as_view(), name="notification-list"),
    path("notifications/<uuid:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("notifications/<uuid:pk>/", NotificationDeleteView.as_view(), name="notification-delete"),
    path("me/notification-preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
]
