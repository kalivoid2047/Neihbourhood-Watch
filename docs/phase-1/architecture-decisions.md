# Phase 1 Architecture Decisions

## Scope

Phase 1 establishes the backend foundation for Neighbourhood Watch Zimbabwe:

- Django REST API project structure.
- Domain schema for required platform entities.
- JWT authentication wiring.
- Role and permission foundation.
- Offline sync schema foundation.
- Conditional PostGIS support for production geospatial queries.
- Docker-based local production topology.

Flutter mobile, Next.js dashboard, Celery jobs, Channels consumers, and MinIO media workflows are intentionally prepared at the boundary but implemented in later phases.

## Decisions

### Backend-First Foundation

The backend owns identity, verification, incident, SOS, notification, audit, analytics, and sync data. Mobile and dashboard clients will consume versioned REST APIs as they are implemented phase by phase.

### Custom User Model

The platform uses a custom email-based user model from the first migration. This avoids a late migration away from Django's default username identity and gives the schema first-class fields for phone number, national ID, role, verification status, address, and coordinates.

### RBAC Model

Django's built-in auth permissions remain available for admin compatibility, but application-level authorization uses custom `Role`, `Permission`, and `RolePermission` tables. This keeps platform roles aligned with the project brief:

- Resident
- Block Captain
- Coordinator
- Police Officer
- System Administrator

### UUIDs, Soft Deletion, and Sync Metadata

All domain entities inherit UUID primary keys, timestamps, `last_modified_at`, and `deleted_at`. UUIDs allow mobile-created offline records to be reconciled without relying on server-generated integer IDs. `last_modified_at` supports delta sync and "last modified wins" conflict resolution in Phase 4.

### PostGIS Without Local GDAL Requirement

Production uses PostgreSQL with PostGIS. The local Windows environment does not currently have GDAL available, so the Django ORM stores latitude and longitude as decimal fields while a conditional PostgreSQL migration adds generated PostGIS geography columns and GiST indexes in production.

This gives Phase 1 a testable local workflow and a production-ready spatial foundation.

### Media Storage Boundary

Media models include file metadata, checksum, metadata JSON, and encryption key references. MinIO and signed URL workflows are deferred to the media phase, but the database contract is already shaped for secure evidence handling.

### Offline-First Boundary

The `SyncQueue` model stores client-side mutations, idempotency keys, retry state, local modification time, and conflict status. Sync APIs and mobile Drift storage are deferred to Phase 4.

