# Next Phases Roadmap

## Phase 3: Incident Reporting APIs

- Implement incident CRUD endpoints for residents, block captains, coordinators, police officers, and administrators.
- Add media evidence upload APIs with validation for image, video, and audio MIME types.
- Add incident status transition services for pending, verified, investigating, resolved, and closed states.
- Enforce RBAC for own incidents, neighborhood incidents, critical incidents, and evidence access.
- Add audit logging for incident creation, verification, assignment, status changes, and media upload.
- Add tests for incident permissions, validation, media handling, and status workflows.

## Phase 4: Geospatial Queries (PostGIS)

- Add repository/service layer for radius searches and neighborhood geofencing.
- Implement affected-area detection for verified incidents.
- Add PostGIS query tests in a PostgreSQL/PostGIS test profile.
- Add endpoints for nearby incidents, neighborhood risk summaries, and hotspot inputs.
- Keep SQLite-compatible unit tests for non-spatial business logic.

## Phase 5: Notification Engine

- Implement notification dispatch service with provider interfaces for Firebase Cloud Messaging, SMS, and dashboard notifications.
- Add Celery tasks for asynchronous fanout, retries, and failure tracking.
- Implement alert fanout for verified incidents and active SOS sessions.
- Add notification preference and device-token APIs.
- Add tests for fanout targeting, retry behavior, failure recording, and notification history.

