from rest_framework import generics, permissions

from .models import AnalyticsSnapshot
from .serializers import AnalyticsSnapshotSerializer


class AnalyticsSnapshotListView(generics.ListAPIView):
    """GET /api/analytics/ — list analytics snapshots.

    Query params:
        ``neighborhood`` (UUID) — filter by neighborhood.
        ``snapshot_type`` (str) — filter by type (e.g. ``daily_risk``).
    """

    serializer_class = AnalyticsSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = AnalyticsSnapshot.objects.order_by("-period_start")
        nb = self.request.query_params.get("neighborhood")
        if nb:
            qs = qs.filter(neighborhood_id=nb)
        snap_type = self.request.query_params.get("snapshot_type")
        if snap_type:
            qs = qs.filter(snapshot_type=snap_type)
        return qs
