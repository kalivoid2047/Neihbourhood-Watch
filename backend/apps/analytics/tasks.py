"""Celery tasks for generating periodic analytics snapshots.

``generate_daily_snapshots`` runs nightly and writes one
:class:`~apps.analytics.models.AnalyticsSnapshot` per active neighborhood,
using the existing :func:`~apps.incidents.services.IncidentGeospatialService.neighborhood_risk_summary`
service to populate the metrics.
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def generate_daily_snapshots() -> dict:
    """Generate a ``daily_risk`` snapshot for every active neighborhood."""
    from apps.analytics.models import AnalyticsSnapshot
    from apps.incidents.services import IncidentGeospatialService
    from apps.neighborhoods.models import Neighborhood

    now = timezone.now()
    period_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

    neighborhoods = Neighborhood.objects.filter(is_active=True, deleted_at__isnull=True)
    created = 0

    for hood in neighborhoods:
        metrics = IncidentGeospatialService.neighborhood_risk_summary(
            neighborhood_id=hood.pk,
            days=1,
        )
        AnalyticsSnapshot.objects.create(
            snapshot_type="daily_risk",
            neighborhood=hood,
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            source_version="phase6",
        )
        created += 1

    return {"snapshots_created": created}
