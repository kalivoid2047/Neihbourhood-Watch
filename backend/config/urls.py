"""Project URL configuration."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.views import APIRootView, HealthCheckView, MetricsView, OpenAPISchemaView, ProtectedMediaView


urlpatterns = [
    path("", RedirectView.as_view(url="/api/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/", APIRootView.as_view(), name="api-root"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.incidents.urls")),
    path("api/", include("apps.neighborhoods.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.sync.urls")),
    path("api/", include("apps.analytics.urls")),
    path("api/", include("apps.sos.urls")),
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/metrics/", MetricsView.as_view(), name="metrics"),
    path("api/schema/", OpenAPISchemaView.as_view(), name="openapi-schema"),
    path("api/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/media/<path:path>", ProtectedMediaView.as_view(), name="protected-media"),
]
