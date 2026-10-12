from django.urls import path

from .consumers import IncidentConsumer, NotificationConsumer

websocket_urlpatterns = [
    path("ws/incidents/<uuid:incident_id>/", IncidentConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
