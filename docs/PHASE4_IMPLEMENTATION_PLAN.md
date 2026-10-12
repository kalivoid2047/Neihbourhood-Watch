# Phase 4: Geospatial Queries — Implementation Notes

## Overview

Phase 4 adds location-based incident discovery, neighborhood risk metrics, and
heatmap aggregation.  All spatial computation uses pure-Python Haversine math on
the existing `latitude`/`longitude` DecimalFields so the feature works on both
SQLite (dev/test) and PostgreSQL (production) without requiring GDAL or PostGIS.

---

## What Was Implemented

### Service layer (`apps/incidents/services.py`)

**`_haversine_m(lat1, lon1, lat2, lon2) → float`**
Great-circle distance in metres between two lat/lon points.
Used internally by the service methods below.

**`IncidentGeospatialService`**

| Method | Description |
|--------|-------------|
| `nearby_incidents(lat, lon, radius_m, base_queryset, statuses)` | Returns `[(distance_m, incident)]` tuples, sorted nearest-first.  Uses a bounding-box ORM pre-filter for efficiency, then exact Haversine. |
| `incidents_in_neighborhood(neighborhood_id, statuses)` | Returns incidents whose `neighborhood` FK matches, with optional status filter. |
| `incident_heatmap(neighborhood_id, bounds, days, grid_size_deg)` | Aggregates incidents into a lat/lon grid (`0.01°` ≈ 1 km by default).  Accepts either a `neighborhood_id` or a bounding-box tuple.  Filters by `occurred_at` over the last `days` days. |
| `notify_affected_users(incident_id, radius_m)` | Returns `User` queryset — members of neighborhoods whose centroid is within `radius_m` metres of the incident.  Skips neighborhoods with null centroids. |
| `neighborhood_risk_summary(neighborhood_id, days)` | Returns counts by severity, category, and status for the last `days` days, filtering on `occurred_at`. |

### Serializers (`apps/incidents/serializers.py`)

| Serializer | Purpose |
|------------|---------|
| `NearbyIncidentSerializer` | Extends `IncidentListSerializer` with `distance_m` (read from `obj._distance_m`). |
| `HeatmapCellSerializer` | One grid cell: `{latitude, longitude, count, severity_counts}`. |
| `NeighborhoodRiskSummarySerializer` | `{neighborhood_id, days, total_incidents, by_severity, by_category, by_status}`. |

### Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/incidents/nearby/` | Incidents within radius. Params: `latitude`, `longitude`, `radius_m` (default 5000, max 50000), `status` (repeatable). |
| `GET` | `/api/incidents/heatmap/` | Grid heatmap. Params: `neighborhood_id` OR `bounds` (min_lat,min_lon,max_lat,max_lon), `days` (default 7). |
| `GET` | `/api/neighborhoods/` | List active neighborhoods. |
| `GET` | `/api/neighborhoods/{id}/` | Neighborhood detail. |
| `GET` | `/api/neighborhoods/{id}/risk_summary/` | Risk metrics. Param: `days` (default 30). |

### New files

| File | Purpose |
|------|---------|
| `apps/neighborhoods/views.py` | `NeighborhoodViewSet` (read-only + `risk_summary` action). |
| `apps/neighborhoods/urls.py` | DRF router wiring for neighborhoods. |
| `apps/incidents/tests/test_phase4_geospatial.py` | 58 tests covering service methods and all new API endpoints. |

### Modified files

| File | Change |
|------|--------|
| `apps/incidents/services.py` | Added `_haversine_m` helper and `IncidentGeospatialService`. |
| `apps/incidents/serializers.py` | Added `NearbyIncidentSerializer`, `HeatmapCellSerializer`, `NeighborhoodRiskSummarySerializer`. |
| `apps/incidents/views.py` | Added `nearby` and `heatmap` actions to `IncidentViewSet`. |
| `apps/neighborhoods/serializers.py` | Re-exports `NeighborhoodRiskSummarySerializer` from `incidents`. |
| `config/urls.py` | Includes `apps.neighborhoods.urls`. |

---

## Design Decisions

### Pure-Python Haversine instead of PostGIS

The production PostgreSQL database uses PostGIS geography columns (via the
conditional migration in `core.0002_postgis_foundation`), but the test
environment runs SQLite and GDAL is not installed on Windows.  The pure-Python
implementation avoids that dependency while delivering identical results.  A
future migration to `ST_DWithin` / `ST_Distance` PostGIS functions is a
non-breaking optimisation — the service interface stays the same.

### Bounding-box pre-filter

`nearby_incidents` pre-filters with an ORM range query on the decimal lat/lon
columns before running the exact Haversine loop in Python.  This limits the
Python-side work to a tight geographic band around the query point, keeping the
endpoint fast even with large incident tables.

### `occurred_at` vs `created_at` for time windows

The heatmap and risk-summary methods filter by `occurred_at__gte=cutoff` rather
than `created_at`.  This gives operationally meaningful results: "incidents that
happened in the last N days" is more useful for heatmaps than "incidents reported
in the last N days".

### Role-based queryset passthrough in `nearby`

The `nearby` API action calls `self.get_queryset()` as the `base_queryset`, so
role-based visibility rules (residents see only their neighborhood, coordinators
see their neighborhoods, admins see all) apply automatically to spatial queries
as well — no separate permission logic is needed.

---

## Test Coverage

58 tests across:

- `HaversineTests` — correctness of `_haversine_m` (zero distance, 1-degree reference, symmetry)
- `NearbyIncidentsServiceTests` — radius include/exclude, sort order, distance sign, status filter, base-queryset passthrough
- `IncidentsInNeighborhoodServiceTests` — FK filter, status filter, empty case
- `IncidentHeatmapServiceTests` — cell aggregation, same-cell grouping, separate-cell separation, severity counts, days filter, bounds filter, missing params
- `NotifyAffectedUsersServiceTests` — near/far membership, nonexistent incident, null-centroid safety
- `NeighborhoodRiskSummaryServiceTests` — total count, by-severity, by-category, by-status, days filter, empty case, key presence
- `NearbyIncidentsAPITests` — auth gate, valid params, validation errors, distance field, radius exclusion, status filter
- `HeatmapAPITests` — auth gate, neighborhood_id path, bounds path, missing params, invalid bounds, cell schema
- `NeighborhoodListAPITests` — auth gate, 200, active neighborhoods, inactive exclusion
- `NeighborhoodRiskSummaryAPITests` — auth gate, 200, schema, days param, invalid days, count accuracy
