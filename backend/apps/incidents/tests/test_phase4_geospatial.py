"""
Tests for Phase 4 — Geospatial Queries.

All tests run against SQLite (dev/CI) using the pure-Python Haversine
implementation in IncidentGeospatialService.  No GDAL or PostGIS is required.

Coverage:
  Service — nearby_incidents (radius, sorting, status filter)
  Service — incidents_in_neighborhood (FK filter, status filter)
  Service — incident_heatmap (grid aggregation, severity counts, bounds)
  Service — notify_affected_users (radius, null-centroid safety)
  Service — neighborhood_risk_summary (counts, groupings, days filter)
  API — GET /api/incidents/nearby/
  API — GET /api/incidents/heatmap/
  API — GET /api/neighborhoods/
  API — GET /api/neighborhoods/{id}/risk-summary/
"""

import math
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.incidents.models import Incident
from apps.incidents.services import IncidentGeospatialService, _haversine_m
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership


PASSWORD = "ZimSecure123!"

# Reference point: central Harare
REF_LAT = -17.8252
REF_LON = 31.0335

# Offsets — 1 degree latitude ≈ 111 320 m
_LAT_PER_M = 1 / 111_320


def _offset_lat(base_lat, metres):
    """Return a latitude *metres* north of *base_lat*."""
    return base_lat + metres * _LAT_PER_M


def create_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def create_user(
    *,
    email="user@example.com",
    phone_number="+263771000001",
    national_id="63-100001A01",
    role_code=Role.Code.COORDINATOR,
):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name="Test User",
        phone_number=phone_number,
        national_id=national_id,
        role=create_role(role_code),
    )


def create_neighborhood(
    *,
    name="Test Hood",
    code="test-hood",
    lat=REF_LAT,
    lon=REF_LON,
    radius=5000,
):
    return Neighborhood.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "city": "Harare",
            "province": "Harare",
            "centroid_latitude": str(lat),
            "centroid_longitude": str(lon),
            "alert_radius_m": radius,
        },
    )[0]


def create_incident(user, neighborhood=None, *, lat=REF_LAT, lon=REF_LON,
                    status=Incident.Status.PENDING, severity=Incident.Severity.BLUE,
                    category=Incident.Category.THEFT, days_ago=0):
    occurred = timezone.now() - timedelta(days=days_ago)
    return Incident.objects.create(
        reporter=user,
        neighborhood=neighborhood,
        title="Test Incident",
        description="Something happened.",
        category=category,
        severity=severity,
        status=status,
        latitude=str(lat),
        longitude=str(lon),
        occurred_at=occurred,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper: _haversine_m
# ─────────────────────────────────────────────────────────────────────────────

class HaversineTests(TestCase):
    def test_same_point_is_zero(self):
        self.assertAlmostEqual(_haversine_m(REF_LAT, REF_LON, REF_LAT, REF_LON), 0.0, places=1)

    def test_one_degree_latitude_is_approx_111km(self):
        dist = _haversine_m(0, 0, 1, 0)
        self.assertAlmostEqual(dist, 111_320, delta=200)

    def test_north_south_symmetry(self):
        d1 = _haversine_m(REF_LAT, REF_LON, REF_LAT + 0.1, REF_LON)
        d2 = _haversine_m(REF_LAT + 0.1, REF_LON, REF_LAT, REF_LON)
        self.assertAlmostEqual(d1, d2, places=3)


# ─────────────────────────────────────────────────────────────────────────────
# Service: nearby_incidents
# ─────────────────────────────────────────────────────────────────────────────

class NearbyIncidentsServiceTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.hood = create_neighborhood()
        # 500 m north of reference
        self.close_lat = _offset_lat(REF_LAT, 500)
        # 10 km north of reference
        self.far_lat = _offset_lat(REF_LAT, 10_000)

    def test_incident_within_radius_is_returned(self):
        inc = create_incident(self.user, lat=self.close_lat, lon=REF_LON)
        results = IncidentGeospatialService.nearby_incidents(REF_LAT, REF_LON, 1000)
        ids = [i.pk for _, i in results]
        self.assertIn(inc.pk, ids)

    def test_incident_beyond_radius_is_excluded(self):
        inc = create_incident(self.user, lat=self.far_lat, lon=REF_LON)
        results = IncidentGeospatialService.nearby_incidents(REF_LAT, REF_LON, 5000)
        ids = [i.pk for _, i in results]
        self.assertNotIn(inc.pk, ids)

    def test_results_sorted_nearest_first(self):
        near = create_incident(self.user, lat=_offset_lat(REF_LAT, 300), lon=REF_LON)
        mid = create_incident(self.user, lat=_offset_lat(REF_LAT, 700), lon=REF_LON)
        results = IncidentGeospatialService.nearby_incidents(REF_LAT, REF_LON, 2000)
        ids = [i.pk for _, i in results]
        self.assertLess(ids.index(near.pk), ids.index(mid.pk))

    def test_distance_values_are_positive(self):
        create_incident(self.user, lat=self.close_lat, lon=REF_LON)
        results = IncidentGeospatialService.nearby_incidents(REF_LAT, REF_LON, 1000)
        for dist, _ in results:
            self.assertGreater(dist, 0)

    def test_status_filter_excludes_wrong_status(self):
        pending = create_incident(self.user, lat=self.close_lat, lon=REF_LON, status=Incident.Status.PENDING)
        resolved = create_incident(
            self.user, lat=self.close_lat, lon=REF_LON, status=Incident.Status.RESOLVED,
        )
        results = IncidentGeospatialService.nearby_incidents(
            REF_LAT, REF_LON, 1000, statuses=[Incident.Status.PENDING]
        )
        ids = [i.pk for _, i in results]
        self.assertIn(pending.pk, ids)
        self.assertNotIn(resolved.pk, ids)

    def test_no_incidents_returns_empty_list(self):
        results = IncidentGeospatialService.nearby_incidents(REF_LAT, REF_LON, 1000)
        self.assertEqual(results, [])

    def test_base_queryset_is_respected(self):
        own = create_incident(self.user, lat=self.close_lat, lon=REF_LON)
        other_user = create_user(email="other@example.com", phone_number="+263771000002", national_id="63-100002A02")
        other = create_incident(other_user, lat=self.close_lat, lon=REF_LON)
        base = Incident.objects.filter(reporter=self.user)
        results = IncidentGeospatialService.nearby_incidents(REF_LAT, REF_LON, 1000, base_queryset=base)
        ids = [i.pk for _, i in results]
        self.assertIn(own.pk, ids)
        self.assertNotIn(other.pk, ids)


# ─────────────────────────────────────────────────────────────────────────────
# Service: incidents_in_neighborhood
# ─────────────────────────────────────────────────────────────────────────────

class IncidentsInNeighborhoodServiceTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.hood_a = create_neighborhood(code="hood-a", name="Hood A")
        self.hood_b = create_neighborhood(code="hood-b", name="Hood B")

    def test_returns_incidents_in_correct_neighborhood(self):
        inc_a = create_incident(self.user, self.hood_a)
        inc_b = create_incident(self.user, self.hood_b)
        qs = IncidentGeospatialService.incidents_in_neighborhood(self.hood_a.pk)
        self.assertIn(inc_a, qs)
        self.assertNotIn(inc_b, qs)

    def test_status_filter(self):
        pending = create_incident(self.user, self.hood_a, status=Incident.Status.PENDING)
        resolved = create_incident(self.user, self.hood_a, status=Incident.Status.RESOLVED)
        qs = IncidentGeospatialService.incidents_in_neighborhood(
            self.hood_a.pk, statuses=[Incident.Status.PENDING]
        )
        self.assertIn(pending, qs)
        self.assertNotIn(resolved, qs)

    def test_empty_neighborhood_returns_no_incidents(self):
        qs = IncidentGeospatialService.incidents_in_neighborhood(self.hood_a.pk)
        self.assertEqual(qs.count(), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Service: incident_heatmap
# ─────────────────────────────────────────────────────────────────────────────

class IncidentHeatmapServiceTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.hood = create_neighborhood()

    def test_heatmap_returns_list(self):
        create_incident(self.user, self.hood)
        result = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=30)
        self.assertIsInstance(result, list)

    def test_heatmap_cell_has_required_keys(self):
        create_incident(self.user, self.hood, lat=REF_LAT, lon=REF_LON)
        cells = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=30)
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        for key in ("latitude", "longitude", "count", "severity_counts"):
            self.assertIn(key, cell)

    def test_close_incidents_land_in_same_cell(self):
        # Use a grid-cell centre (−17.82) so that +0.001 stays inside the same 0.01° cell.
        # −17.82  / 0.01 = −1782.0   → rounds to −1782 → centre −17.82
        # −17.819 / 0.01 = −1781.9   → rounds to −1782 → centre −17.82  (same cell)
        cell_lat, cell_lon = -17.82, 31.03
        create_incident(self.user, self.hood, lat=cell_lat, lon=cell_lon)
        create_incident(self.user, self.hood, lat=cell_lat + 0.001, lon=cell_lon + 0.001)
        cells = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=30)
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]["count"], 2)

    def test_distant_incidents_land_in_different_cells(self):
        # 0.02 degrees apart — spans two grid cells
        create_incident(self.user, self.hood, lat=REF_LAT, lon=REF_LON)
        create_incident(self.user, self.hood, lat=REF_LAT + 0.02, lon=REF_LON)
        cells = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=30)
        self.assertEqual(len(cells), 2)

    def test_severity_counts_are_correct(self):
        create_incident(self.user, self.hood, lat=REF_LAT, lon=REF_LON, severity=Incident.Severity.RED)
        create_incident(self.user, self.hood, lat=REF_LAT, lon=REF_LON, severity=Incident.Severity.RED)
        create_incident(self.user, self.hood, lat=REF_LAT, lon=REF_LON, severity=Incident.Severity.BLUE)
        cells = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=30)
        self.assertEqual(len(cells), 1)
        counts = cells[0]["severity_counts"]
        self.assertEqual(counts.get(Incident.Severity.RED), 2)
        self.assertEqual(counts.get(Incident.Severity.BLUE), 1)

    def test_days_filter_excludes_old_incidents(self):
        create_incident(self.user, self.hood, days_ago=2)   # recent — included
        create_incident(self.user, self.hood, days_ago=10)  # old — excluded with days=7
        cells = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=7)
        total = sum(c["count"] for c in cells)
        self.assertEqual(total, 1)

    def test_bounds_filter_works(self):
        inside = create_incident(self.user, lat=REF_LAT, lon=REF_LON)
        outside = create_incident(self.user, lat=REF_LAT + 5, lon=REF_LON + 5)
        bounds = (REF_LAT - 1, REF_LON - 1, REF_LAT + 1, REF_LON + 1)
        cells = IncidentGeospatialService.incident_heatmap(bounds=bounds, days=30)
        total = sum(c["count"] for c in cells)
        self.assertEqual(total, 1)

    def test_requires_neighborhood_or_bounds(self):
        with self.assertRaises(ValueError):
            IncidentGeospatialService.incident_heatmap(days=7)

    def test_empty_neighborhood_returns_empty_list(self):
        cells = IncidentGeospatialService.incident_heatmap(neighborhood_id=self.hood.pk, days=30)
        self.assertEqual(cells, [])


# ─────────────────────────────────────────────────────────────────────────────
# Service: notify_affected_users
# ─────────────────────────────────────────────────────────────────────────────

class NotifyAffectedUsersServiceTests(TestCase):
    def setUp(self):
        self.coordinator = create_user()
        # Neighborhood 500 m north — within 1 km radius
        self.near_hood = create_neighborhood(
            code="near-hood", name="Near Hood",
            lat=_offset_lat(REF_LAT, 500), lon=REF_LON,
        )
        # Neighborhood 15 km north — outside 5 km radius
        self.far_hood = create_neighborhood(
            code="far-hood", name="Far Hood",
            lat=_offset_lat(REF_LAT, 15_000), lon=REF_LON,
        )
        self.near_user = create_user(
            email="near@example.com", phone_number="+263771000003", national_id="63-100003A03",
            role_code=Role.Code.RESIDENT,
        )
        self.far_user = create_user(
            email="far@example.com", phone_number="+263771000004", national_id="63-100004A04",
            role_code=Role.Code.RESIDENT,
        )
        NeighborhoodMembership.objects.create(user=self.near_user, neighborhood=self.near_hood)
        NeighborhoodMembership.objects.create(user=self.far_user, neighborhood=self.far_hood)

        self.incident = create_incident(self.coordinator, lat=REF_LAT, lon=REF_LON)

    def test_user_in_near_neighborhood_is_returned(self):
        users = IncidentGeospatialService.notify_affected_users(self.incident.pk, radius_m=1000)
        self.assertIn(self.near_user, users)

    def test_user_in_far_neighborhood_is_excluded(self):
        users = IncidentGeospatialService.notify_affected_users(self.incident.pk, radius_m=1000)
        self.assertNotIn(self.far_user, users)

    def test_nonexistent_incident_returns_empty(self):
        import uuid
        users = IncidentGeospatialService.notify_affected_users(uuid.uuid4(), radius_m=5000)
        self.assertEqual(list(users), [])

    def test_null_centroid_neighborhood_is_skipped(self):
        null_hood = Neighborhood.objects.create(
            name="No Centroid", code="no-centroid",
            city="Harare", province="Harare",
            centroid_latitude=None, centroid_longitude=None,
        )
        null_user = create_user(
            email="null@example.com", phone_number="+263771000005", national_id="63-100005A05",
            role_code=Role.Code.RESIDENT,
        )
        NeighborhoodMembership.objects.create(user=null_user, neighborhood=null_hood)
        # Should not raise
        users = IncidentGeospatialService.notify_affected_users(self.incident.pk, radius_m=10_000)
        self.assertNotIn(null_user, users)


# ─────────────────────────────────────────────────────────────────────────────
# Service: neighborhood_risk_summary
# ─────────────────────────────────────────────────────────────────────────────

class NeighborhoodRiskSummaryServiceTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.hood = create_neighborhood()

    def test_total_count_is_correct(self):
        for _ in range(3):
            create_incident(self.user, self.hood)
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=30)
        self.assertEqual(summary["total_incidents"], 3)

    def test_by_severity_is_correct(self):
        create_incident(self.user, self.hood, severity=Incident.Severity.RED)
        create_incident(self.user, self.hood, severity=Incident.Severity.RED)
        create_incident(self.user, self.hood, severity=Incident.Severity.BLUE)
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=30)
        self.assertEqual(summary["by_severity"].get(Incident.Severity.RED), 2)
        self.assertEqual(summary["by_severity"].get(Incident.Severity.BLUE), 1)

    def test_by_category_is_correct(self):
        create_incident(self.user, self.hood, category=Incident.Category.THEFT)
        create_incident(self.user, self.hood, category=Incident.Category.ASSAULT)
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=30)
        self.assertEqual(summary["by_category"].get(Incident.Category.THEFT), 1)
        self.assertEqual(summary["by_category"].get(Incident.Category.ASSAULT), 1)

    def test_by_status_is_correct(self):
        create_incident(self.user, self.hood, status=Incident.Status.PENDING)
        create_incident(self.user, self.hood, status=Incident.Status.VERIFIED)
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=30)
        self.assertIn(Incident.Status.PENDING, summary["by_status"])
        self.assertIn(Incident.Status.VERIFIED, summary["by_status"])

    def test_days_filter_excludes_old_incidents(self):
        create_incident(self.user, self.hood, days_ago=5)   # within 7 days
        create_incident(self.user, self.hood, days_ago=15)  # outside 7 days
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=7)
        self.assertEqual(summary["total_incidents"], 1)

    def test_empty_neighborhood_returns_zeros(self):
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=30)
        self.assertEqual(summary["total_incidents"], 0)
        self.assertEqual(summary["by_severity"], {})

    def test_response_contains_required_keys(self):
        summary = IncidentGeospatialService.neighborhood_risk_summary(self.hood.pk, days=30)
        for key in ("neighborhood_id", "days", "total_incidents", "by_severity", "by_category", "by_status"):
            self.assertIn(key, summary)


# ─────────────────────────────────────────────────────────────────────────────
# API: GET /api/incidents/nearby/
# ─────────────────────────────────────────────────────────────────────────────

class NearbyIncidentsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.hood = create_neighborhood()

    def _get(self, params):
        return self.client.get("/api/incidents/nearby/", params)

    def test_requires_authentication(self):
        self.client.logout()
        response = self._get({"latitude": REF_LAT, "longitude": REF_LON})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_200_with_valid_params(self):
        response = self._get({"latitude": REF_LAT, "longitude": REF_LON, "radius_m": 1000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_latitude_returns_400(self):
        response = self._get({"longitude": REF_LON})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_longitude_returns_400(self):
        response = self._get({"latitude": REF_LAT})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_latitude_returns_400(self):
        response = self._get({"latitude": 91, "longitude": REF_LON})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_radius_m_returns_400(self):
        response = self._get({"latitude": REF_LAT, "longitude": REF_LON, "radius_m": 100_000})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_includes_distance_m(self):
        close_lat = _offset_lat(REF_LAT, 200)
        create_incident(self.user, lat=close_lat, lon=REF_LON)
        response = self._get({"latitude": REF_LAT, "longitude": REF_LON, "radius_m": 500})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()
        self.assertGreater(len(results), 0)
        self.assertIn("distance_m", results[0])
        self.assertGreater(results[0]["distance_m"], 0)

    def test_incident_beyond_radius_not_in_response(self):
        far_lat = _offset_lat(REF_LAT, 10_000)
        inc = create_incident(self.user, lat=far_lat, lon=REF_LON)
        response = self._get({"latitude": REF_LAT, "longitude": REF_LON, "radius_m": 5000})
        ids = [r["id"] for r in response.json()]
        self.assertNotIn(str(inc.pk), ids)

    def test_status_filter_param(self):
        pending = create_incident(self.user, lat=_offset_lat(REF_LAT, 100), lon=REF_LON, status=Incident.Status.PENDING)
        resolved = create_incident(self.user, lat=_offset_lat(REF_LAT, 100), lon=REF_LON)
        # Transition resolved to VERIFIED then RESOLVED via direct update to avoid service dep
        Incident.objects.filter(pk=resolved.pk).update(status=Incident.Status.VERIFIED)
        Incident.objects.filter(pk=resolved.pk).update(status=Incident.Status.RESOLVED)
        response = self._get({"latitude": REF_LAT, "longitude": REF_LON, "radius_m": 500, "status": "pending"})
        ids = [r["id"] for r in response.json()]
        self.assertIn(str(pending.pk), ids)
        self.assertNotIn(str(resolved.pk), ids)


# ─────────────────────────────────────────────────────────────────────────────
# API: GET /api/incidents/heatmap/
# ─────────────────────────────────────────────────────────────────────────────

class HeatmapAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.hood = create_neighborhood()

    def test_requires_authentication(self):
        self.client.logout()
        response = self.client.get("/api/incidents/heatmap/", {"neighborhood_id": str(self.hood.pk)})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_200_with_neighborhood_id(self):
        create_incident(self.user, self.hood)
        response = self.client.get("/api/incidents/heatmap/", {"neighborhood_id": str(self.hood.pk), "days": 30})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_returns_200_with_bounds(self):
        create_incident(self.user, lat=REF_LAT, lon=REF_LON)
        bounds = f"{REF_LAT-1},{REF_LON-1},{REF_LAT+1},{REF_LON+1}"
        response = self.client.get("/api/incidents/heatmap/", {"bounds": bounds, "days": 30})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_neighborhood_and_bounds_returns_400(self):
        response = self.client.get("/api/incidents/heatmap/", {"days": 7})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_bounds_returns_400(self):
        response = self.client.get("/api/incidents/heatmap/", {"bounds": "bad,bounds"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cell_schema(self):
        create_incident(self.user, self.hood, lat=REF_LAT, lon=REF_LON)
        response = self.client.get("/api/incidents/heatmap/", {"neighborhood_id": str(self.hood.pk), "days": 30})
        cells = response.json()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        for key in ("latitude", "longitude", "count", "severity_counts"):
            self.assertIn(key, cell)
        self.assertEqual(cell["count"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# API: GET /api/neighborhoods/
# ─────────────────────────────────────────────────────────────────────────────

class NeighborhoodListAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.hood = create_neighborhood()

    def test_list_is_public(self):
        # Phase 8: neighborhood list is public so clients can discover neighborhoods
        # before registration. Unauthenticated requests must return 200.
        self.client.logout()
        response = self.client.get("/api/neighborhoods/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_returns_200(self):
        response = self.client.get("/api/neighborhoods/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_lists_active_neighborhoods(self):
        response = self.client.get("/api/neighborhoods/")
        data = response.json()
        ids = [item["id"] for item in data.get("results", data)]
        self.assertIn(str(self.hood.pk), ids)

    def test_inactive_neighborhood_excluded(self):
        inactive = Neighborhood.objects.create(
            name="Inactive", code="inactive-hood",
            city="Harare", province="Harare",
            centroid_latitude=str(REF_LAT), centroid_longitude=str(REF_LON),
            is_active=False,
        )
        response = self.client.get("/api/neighborhoods/")
        data = response.json()
        ids = [item["id"] for item in data.get("results", data)]
        self.assertNotIn(str(inactive.pk), ids)


# ─────────────────────────────────────────────────────────────────────────────
# API: GET /api/neighborhoods/{id}/risk-summary/
# ─────────────────────────────────────────────────────────────────────────────

class NeighborhoodRiskSummaryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.hood = create_neighborhood()

    def _url(self):
        return f"/api/neighborhoods/{self.hood.pk}/risk_summary/"

    def test_requires_authentication(self):
        self.client.logout()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_200(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_schema(self):
        create_incident(self.user, self.hood)
        response = self.client.get(self._url())
        data = response.json()
        for key in ("neighborhood_id", "days", "total_incidents", "by_severity", "by_category", "by_status"):
            self.assertIn(key, data)

    def test_days_query_param(self):
        create_incident(self.user, self.hood, days_ago=0)
        create_incident(self.user, self.hood, days_ago=20)
        response = self.client.get(self._url(), {"days": 7})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total_incidents"], 1)
        self.assertEqual(response.json()["days"], 7)

    def test_invalid_days_returns_400(self):
        response = self.client.get(self._url(), {"days": "bad"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_total_incidents_reflects_count(self):
        for _ in range(4):
            create_incident(self.user, self.hood)
        response = self.client.get(self._url())
        self.assertEqual(response.json()["total_incidents"], 4)
