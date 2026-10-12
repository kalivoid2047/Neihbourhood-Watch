from django.urls import path

from .views import AnalyticsSnapshotListView

urlpatterns = [
    path("analytics/", AnalyticsSnapshotListView.as_view(), name="analytics-list"),
]
