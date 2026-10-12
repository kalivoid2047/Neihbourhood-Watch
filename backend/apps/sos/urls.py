from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SOSAlertViewSet

router = DefaultRouter()
router.register("sos", SOSAlertViewSet, basename="sos")

urlpatterns = [
    path("", include(router.urls)),
]
