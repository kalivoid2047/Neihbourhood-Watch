# Phase 1 Database Foundation

## Core Database Rules

- UUID primary keys on all platform domain tables.
- `created_at`, `updated_at`, `last_modified_at`, and `deleted_at` on all soft-deletable domain tables.
- Foreign keys for ownership and workflow relationships.
- Indexes on status, role, category, severity, timestamps, and coordinate pairs.
- PostgreSQL/PostGIS generated spatial columns for production radius and heatmap queries.

## Required Entities Covered

| Requirement | Django Model |
| --- | --- |
| Users | `accounts.User` |
| Roles | `accounts.Role` |
| Permissions | `accounts.Permission` |
| Neighborhoods | `neighborhoods.Neighborhood` |
| VerificationRequests | `accounts.VerificationRequest` |
| Incidents | `incidents.Incident` |
| IncidentMedia | `incidents.IncidentMedia` |
| Notifications | `notifications.Notification` |
| SOSAlerts | `sos.SOSAlert` |
| EmergencyContacts | `accounts.EmergencyContact` |
| AuditLogs | `audit.AuditLog` |
| DeviceTokens | `accounts.DeviceToken` |
| SyncQueue | `sync.SyncQueue` |
| AnalyticsSnapshots | `analytics.AnalyticsSnapshot` |

## Production Spatial Columns

The conditional `core.0002_postgis_foundation` migration adds:

- `accounts_user.location` as `geography(Point, 4326)`.
- `neighborhoods_neighborhood.boundary` as `geometry(MultiPolygon, 4326)`.
- `neighborhoods_neighborhood.centroid` as `geography(Point, 4326)`.
- `incidents_incident.location` as `geography(Point, 4326)`.
- `sos_sosalert.current_location` as `geography(Point, 4326)`.

Each spatial column gets a GiST index for efficient geofence, radius, clustering, and heatmap queries.

## Local Development Note

Local tests use SQLite because GDAL is not installed in this Windows environment. Production Docker installs native GIS libraries and uses the PostGIS database service.

