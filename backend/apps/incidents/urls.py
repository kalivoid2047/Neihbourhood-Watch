from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import IncidentViewSet, IncidentMediaDetailView

router = DefaultRouter()
router.register("incidents", IncidentViewSet, basename="incidents")

urlpatterns = [
    path("", include(router.urls)),
    path("media/<uuid:pk>/", IncidentMediaDetailView.as_view(), name="incident-media-detail"),
]
