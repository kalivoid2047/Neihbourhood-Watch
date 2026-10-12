"""Services for incident status transitions and geospatial queries."""

import math
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, F
from django.utils import timezone

from apps.audit.services import create_audit_log, snapshot_model

from .models import Incident

# ──────────────────────────────────────────────────────────────────────────────
# Geospatial helpers
# ──────────────────────────────────────────────────────────────────────────────

_EARTH_RADIUS_M = 6_371_000  # mean radius of Earth in metres


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Return the great-circle distance in metres between two (lat, lon) points."""
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlam = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


class IncidentGeospatialService:
    """Spatial query helpers that work on both SQLite (dev/test) and PostGIS (prod).

    All distance computation uses pure-Python Haversine on ``latitude``/
    ``longitude`` DecimalFields, with an ORM bounding-box pre-filter for
    efficiency.  No GDAL / PostGIS extension is required in the test environment.
    """

    # ── Distance / nearby ────────────────────────────────────────────────────

    @staticmethod
    def nearby_incidents(lat, lon, radius_m, base_queryset=None, statuses=None):
        """Return incidents within *radius_m* metres of *(lat, lon)*.

        Args:
            lat: Reference latitude (float or Decimal).
            lon: Reference longitude (float or Decimal).
            radius_m: Search radius in metres.
            base_queryset: Optional pre-scoped queryset (e.g. role-filtered). If
                None, the full Incident manager is used.
            statuses: Optional list of ``Incident.Status`` values to filter on.

        Returns:
            List of ``(distance_m, incident)`` tuples sorted nearest-first.
        """
        qs = base_queryset if base_queryset is not None else Incident.objects.all()

        if statuses:
            qs = qs.filter(status__in=statuses)

        # Bounding-box pre-filter (avoids a full table scan in Python).
        lat_f = float(lat)
        lon_f = float(lon)
        lat_delta = radius_m / 111_320
        # Guard against cos(90°) → 0 division.
        lon_delta = radius_m / (111_320 * max(math.cos(math.radians(lat_f)), 1e-6))
        qs = qs.filter(
            latitude__range=(lat_f - lat_delta, lat_f + lat_delta),
            longitude__range=(lon_f - lon_delta, lon_f + lon_delta),
        )

        # Exact Haversine filter.
        results = []
        for incident in qs:
            dist = _haversine_m(lat, lon, incident.latitude, incident.longitude)
            if dist <= radius_m:
                results.append((dist, incident))

        results.sort(key=lambda pair: pair[0])
        return results  # list of (distance_m, incident) tuples

    # ── Neighborhood containment ──────────────────────────────────────────────

    @staticmethod
    def incidents_in_neighborhood(neighborhood_id, statuses=None):
        """Return all incidents whose ``neighborhood`` FK matches *neighborhood_id*.

        Falls back gracefully: incidents without a neighborhood FK are excluded.
        """
        qs = Incident.objects.filter(neighborhood_id=neighborhood_id)
        if statuses:
            qs = qs.filter(status__in=statuses)
        return qs

    # ── Heatmap ──────────────────────────────────────────────────────────────

    @staticmethod
    def incident_heatmap(neighborhood_id=None, bounds=None, days=7, grid_size_deg=0.01):
        """Aggregate incidents into a lat/lon grid for heatmap rendering.

        Either *neighborhood_id* or *bounds* must be supplied.

        Args:
            neighborhood_id: Filter to a specific neighborhood.
            bounds: ``(min_lat, min_lon, max_lat, max_lon)`` bounding box tuple.
            days: Look-back window in days (default 7).
            grid_size_deg: Grid cell size in decimal degrees (default 0.01 ≈ 1 km).

        Returns:
            List of dicts ``{latitude, longitude, count, severity_counts}``,
            sorted descending by count.
        """
        cutoff = timezone.now() - timedelta(days=days)
        qs = Incident.objects.filter(occurred_at__gte=cutoff)

        if neighborhood_id is not None:
            qs = qs.filter(neighborhood_id=neighborhood_id)
        elif bounds is not None:
            min_lat, min_lon, max_lat, max_lon = bounds
            qs = qs.filter(
                latitude__range=(min_lat, max_lat),
                longitude__range=(min_lon, max_lon),
            )
        else:
            raise ValueError("Either neighborhood_id or bounds must be provided.")

        grid = defaultdict(lambda: {"count": 0, "severity_counts": {}})
        for row in qs.values("latitude", "longitude", "severity"):
            glat = round(round(float(row["latitude"]) / grid_size_deg) * grid_size_deg, 6)
            glon = round(round(float(row["longitude"]) / grid_size_deg) * grid_size_deg, 6)
            key = (glat, glon)
            grid[key]["count"] += 1
            sev = row["severity"]
            grid[key]["severity_counts"][sev] = grid[key]["severity_counts"].get(sev, 0) + 1

        return [
            {
                "latitude": k[0],
                "longitude": k[1],
                "count": v["count"],
                "severity_counts": v["severity_counts"],
            }
            for k, v in sorted(grid.items(), key=lambda x: -x[1]["count"])
        ]

    # ── Affected users ────────────────────────────────────────────────────────

    @staticmethod
    def notify_affected_users(incident_id, radius_m):
        """Return distinct users whose primary neighborhood centroid is within
        *radius_m* metres of the incident location.

        Users without a valid neighborhood membership centroid are excluded.
        """
        from apps.accounts.models import User
        from apps.neighborhoods.models import Neighborhood

        try:
            incident = Incident.objects.get(pk=incident_id)
        except Incident.DoesNotExist:
            return User.objects.none()

        neighborhoods = Neighborhood.objects.filter(
            is_active=True,
            centroid_latitude__isnull=False,
            centroid_longitude__isnull=False,
        )

        affected_ids = [
            nbhd.pk
            for nbhd in neighborhoods
            if _haversine_m(
                incident.latitude, incident.longitude,
                nbhd.centroid_latitude, nbhd.centroid_longitude,
            ) <= radius_m
        ]

        return User.objects.filter(
            neighborhood_memberships__neighborhood_id__in=affected_ids,
            neighborhood_memberships__deleted_at__isnull=True,
        ).distinct()

    # ── Risk summary ──────────────────────────────────────────────────────────

    @staticmethod
    def neighborhood_risk_summary(neighborhood_id, days=30):
        """Return a risk-metric dict for a neighborhood over the last *days* days.

        The returned dict has the shape::

            {
                "neighborhood_id": str,
                "days": int,
                "total_incidents": int,
                "by_severity": {severity: count, ...},
                "by_category": {category: count, ...},
                "by_status":   {status: count, ...},
            }
        """
        cutoff = timezone.now() - timedelta(days=days)
        qs = Incident.objects.filter(
            neighborhood_id=neighborhood_id,
            occurred_at__gte=cutoff,
        )

        total = qs.count()
        by_severity = dict(qs.values("severity").annotate(n=Count("id")).values_list("severity", "n"))
        by_category = dict(qs.values("category").annotate(n=Count("id")).values_list("category", "n"))
        by_status = dict(qs.values("status").annotate(n=Count("id")).values_list("status", "n"))

        return {
            "neighborhood_id": str(neighborhood_id),
            "days": days,
            "total_incidents": total,
            "by_severity": by_severity,
            "by_category": by_category,
            "by_status": by_status,
        }


class IncidentStatusTransitionService:
    """Handles incident status state machine with audit logging."""

    VALID_TRANSITIONS = {
        Incident.Status.PENDING: [Incident.Status.VERIFIED, Incident.Status.CLOSED],
        Incident.Status.VERIFIED: [
            Incident.Status.INVESTIGATING,
            Incident.Status.CLOSED,
        ],
        Incident.Status.INVESTIGATING: [
            Incident.Status.RESOLVED,
            Incident.Status.CLOSED,
        ],
        Incident.Status.RESOLVED: [Incident.Status.CLOSED],
        Incident.Status.CLOSED: [],
    }

    @classmethod
    def can_transition(cls, current_status: str, new_status: str) -> bool:
        """Check if transition is valid."""
        return new_status in cls.VALID_TRANSITIONS.get(current_status, [])

    @classmethod
    def transition(cls, incident: Incident, new_status: str, actor, request=None) -> bool:
        """
        Attempt status transition with validation and audit logging.
        Returns True if successful, False if invalid transition.
        """
        if not cls.can_transition(incident.status, new_status):
            return False

        before = snapshot_model(incident, fields=["status", "verified_by", "verified_at"])
        incident.status = new_status
        incident.sync_version = F("sync_version") + 1

        # Track verification event
        if new_status == Incident.Status.VERIFIED and incident.verified_by is None:
            incident.verified_by = actor
            incident.verified_at = timezone.now()

        incident.save(update_fields=["status", "verified_by", "verified_at", "sync_version", "updated_at", "last_modified_at"])
        incident.refresh_from_db(fields=["sync_version"])

        after = snapshot_model(incident, fields=["status", "verified_by", "verified_at"])
        create_audit_log(
            action=f"incident_status_changed_to_{new_status}",
            actor=actor,
            entity=incident,
            request=request,
            before=before,
            after=after,
            metadata={"new_status": new_status},
        )

        if new_status == Incident.Status.VERIFIED:
            from apps.notifications.services import NotificationDispatchService  # lazy – avoids circular
            NotificationDispatchService.dispatch_incident_alert(incident)

        return True

    @classmethod
    def assign(cls, incident: Incident, assigned_to, actor, request=None) -> None:
        """Assign incident with audit logging."""
        before = snapshot_model(incident, fields=["assigned_to"])
        incident.assigned_to = assigned_to
        incident.sync_version = F("sync_version") + 1
        incident.save(update_fields=["assigned_to", "sync_version", "updated_at", "last_modified_at"])
        incident.refresh_from_db(fields=["sync_version"])

        after = snapshot_model(incident, fields=["assigned_to"])
        create_audit_log(
            action="incident_assigned",
            actor=actor,
            entity=incident,
            request=request,
            before=before,
            after=after,
            metadata={"assigned_to_id": str(assigned_to.id) if assigned_to else None},
        )
