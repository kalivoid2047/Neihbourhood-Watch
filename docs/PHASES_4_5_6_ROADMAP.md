# Implementation Roadmap: Phases 4-6

## Phase 4: Geospatial Queries (PostGIS)

Implement location-based incident discovery and neighborhood geofencing for the production PostgreSQL environment.

### Objectives

1. **Radius Searches**: Find incidents within X meters of user location.
2. **Neighborhood Geofencing**: Determine if incident is inside neighborhood boundary.
3. **Risk Heatmaps**: Aggregate incident severity/count by area for dashboard visualization.
4. **Affected Area Detection**: Automatically notify users in radius of verified incident.

### Implementation Plan

**Services** (`apps/incidents/services.py`):
- `IncidentGeospatialService`:
  - `nearby_incidents(lat, lon, radius_m, statuses)` — Query by distance.
  - `incidents_in_neighborhood(neighborhood_id)` — Query by boundary.
  - `incident_heatmap(neighborhood_id, days=7)` — Aggregate by grid.
  - `notify_affected_users(incident_id, radius_m)` — Get users to notify.

**Views** (`apps/incidents/views.py`):
- New endpoints:
  - `GET /api/incidents/nearby/?latitude=X&longitude=Y&radius_m=5000` — Nearby incidents.
  - `GET /api/neighborhoods/{id}/risk-summary/` — Neighborhood risk stats.
  - `GET /api/incidents/heatmap/?bounds=...` — Grid-based heatmap for map tiles.

**Tests** (`apps/incidents/tests/test_postgis_queries.py`):
- Maintain SQLite tests for non-spatial logic (existing).
- Add PostgreSQL-only test profile for spatial queries.
- Test radius, boundary, heatmap, and affected-user queries.
- Test edge cases (null locations, invalid bounds, timeouts).

**Database**:
- Use existing conditional migration `core.0002_postgis_foundation`.
- Local dev: SQLite decimal fields (no GIS).
- Production: PostGIS geography columns + GiST indexes.

### Expected Deliverables

- 8-10 geospatial API endpoints.
- 15-20 spatial query tests.
- Heatmap rendering support (grid-based or clustering).

---

## Phase 5: Notification Engine

Implement multi-channel notification dispatch for incident alerts, SOS responses, and user messages.

### Objectives

1. **Multi-Provider Support**: Firebase Cloud Messaging (FCM), SMS (Twilio/SendGrid), in-app.
2. **Asynchronous Dispatch**: Celery tasks for fanout and retries.
3. **Incident Alert Fanout**: Notify neighborhood on verified incidents.
4. **SOS Dispatch**: Alert emergency contacts and nearby responders.
5. **Notification History**: Track delivery, read status, and failures.

### Implementation Plan

**Models**:
- `NotificationPreference` — User notification opt-ins per channel.
- `NotificationTemplate` — Templated messages for incidents, SOS, etc.
- Existing `Notification` model expanded for delivery tracking.

**Services** (`apps/notifications/services.py`):
- `NotificationDispatchService`:
  - `dispatch(target_users, message, channels, priority)` — Queue async fanout.
  - `resolve_recipients(incident_id, radius_m)` — Get notify-list for incident.
  - `notify_emergency_contacts(sos_alert_id)` — SOS emergency contact dispatch.
- Provider interfaces (abstract base classes):
  - `FCMProvider` — Firebase Cloud Messaging.
  - `SMSProvider` — Twilio or SendGrid.
  - `InAppProvider` — Write to Notification model.

**Celery Tasks** (`apps/notifications/tasks.py`):
- `send_notifications_batch(notification_ids)` — Batch dispatch.
- `retry_failed_notifications()` — Hourly retry of failures.
- `cleanup_old_notifications()` — Archive old records.

**Views**:
- `GET /api/me/notifications/` — List user notifications (paginated).
- `PATCH /api/notifications/{id}/read/` — Mark as read.
- `DELETE /api/notifications/{id}/` — Soft-delete.
- `POST /api/me/notification-preferences/` — Set user channel preferences.

**Tests**:
- 20-25 tests covering dispatch, retries, templating, and provider mocking.
- Test failed delivery handling and backoff.
- Test SOS emergency contact notification.
- Test rate limiting (don't spam users).

### Expected Deliverables

- 3-4 notification dispatch endpoints.
- 2-3 provider adapters.
- Celery task integration.
- 20+ notification tests.

---

## Phase 6: Mobile & Dashboard Frontend Polish

Finalize React and Flutter clients with authentication, real-time updates, and map visualization.

### Objectives

1. **React Dashboard**: Coordinator incident management, verification, assignment.
2. **Flutter Mobile**: Resident incident reporting, notifications, emergency SOS.
3. **Real-Time**: WebSocket or Server-Sent Events (SSE) for live incident updates.
4. **Maps**: Leaflet or Google Maps for incident location and heatmaps.
5. **Offline Support**: Service workers and IndexedDB for React; Drift for Flutter.

### Implementation Plan

**React Dashboard** (`frontend/`):
- Pages:
  - **Home**: Dashboard with stats, recent incidents, alerts.
  - **Incidents**: Table with filtering, detail modal, status transitions.
  - **Verification Queue**: Coordinator-only flow to approve/reject residents.
  - **Users**: Manage roles and permissions (admins only).
  - **Settings**: Edit profile, notification preferences.
- Real-time: WebSocket or SSE subscription to incident updates.
- Maps: Leaflet with GeoJSON incident markers, heatmap layer.

**Flutter Mobile** (`mobile/` — new):
- Screens:
  - **Auth**: Login, OTP verification, registration.
  - **Report**: Create incident with photo evidence, location picker.
  - **Incidents**: List visible incidents, filter by neighborhood/status.
  - **SOS**: Emergency button, auto-SMS to emergency contacts.
  - **Notifications**: Alert list with action buttons.
  - **Profile**: Edit user details, device token registration.
- Offline-first: Drift local database, sync via SyncQueue.
- Real-time: WebSocket connection to notification stream.

**Backend Enhancements**:
- WebSocket consumers (`apps/core/consumers.py`):
  - IncidentUpdateConsumer — Broadcast incident status changes.
  - NotificationConsumer — Real-time notification delivery.
- Sync API:
  - `POST /api/sync/` — Delta sync for offline changes.
  - `GET /api/sync/queue/` — Retrieve pending mutations for mobile.

**Tests**:
- 15-20 tests for React components (Jest/RTL).
- 15-20 tests for Flutter widgets (flutter_test).
- 10-15 integration tests for WebSocket consumers.

### Expected Deliverables

- Functional React dashboard with auth, incidents, verification, maps.
- Flutter mobile app with reporting, SOS, notifications, offline sync.
- WebSocket real-time incident and notification streams.
- Maps integration (incidents, heatmaps, neighborhoods).

---

## Implementation Priority & Timeline

### Q1 2025

- **Phase 4** (Weeks 1-3): Geospatial queries.
  - PostGIS repository layer.
  - Nearby incidents, risk heatmap endpoints.
  - Spatial query tests.
  
- **Phase 5** (Weeks 4-6): Notification engine.
  - Multi-provider dispatch service.
  - FCM, SMS, in-app providers.
  - Celery task integration.
  - Notification tests.

### Q2 2025

- **Phase 6** (Weeks 1-4): Frontend Polish.
  - React dashboard.
  - Flutter mobile app.
  - WebSocket real-time.
  - Maps visualization.

### Q3 2025

- **Production Hardening**:
  - Security audit (OWASP Top 10).
  - Load testing (k6 or Locust).
  - Performance optimization (caching, indexing).
  - Disaster recovery & backup testing.
  - Documentation & runbooks.

- **Deployment**:
  - Kubernetes manifests.
  - CI/CD pipeline (GitHub Actions).
  - Monitoring (Prometheus, Grafana).
  - Logging (ELK or CloudWatch).

---

## Tech Stack Decisions

| Component | Technology | Rationale |
| --- | --- | --- |
| Backend | Django 5 + DRF | Type-safe, ORM, mature ecosystem. |
| Database | PostgreSQL + PostGIS | Reliable RDBMS, spatial support. |
| Cache | Redis | Sessions, task queue, real-time. |
| Task Queue | Celery | Distributed task processing. |
| Real-Time | Django Channels (WebSocket) | Integrates with Django auth. |
| Maps | Leaflet + Turf.js | Lightweight, open-source. |
| Frontend (Web) | React 18 + Vite | Fast build, hooks, modern DX. |
| Frontend (Mobile) | Flutter | Single codebase, native perf. |
| Offline (Web) | Service Workers + IndexedDB | Standard web API. |
| Offline (Mobile) | Drift (SQLite) | Type-safe DB, sync support. |
| Storage | MinIO (S3-compatible) | Self-hosted, incident evidence. |
| Containerization | Docker + Docker Compose | Dev parity, multi-service. |
| Deployment | Kubernetes | Scalability, self-healing. |

---

## Success Metrics

By end of Phase 6:

- **Backend**: 60+ endpoints, 80+ tests, sub-200ms P95 latency.
- **Frontend**: Responsive React dashboard, functional Flutter app, <3s load time.
- **Real-Time**: Live incident updates, <1s notification delivery.
- **Reliability**: 99.5% uptime, automated backups, failover tested.
- **Security**: HTTPS enforced, JWT expiry, rate limiting, OWASP A1-A4 mitigated.
- **Documentation**: API docs, runbooks, architecture ADRs, deployment guide.

---

## Rollout Strategy

### Beta (Internal)
- Deploy to staging Kubernetes cluster.
- Invite 10-20 internal testers (devs, stakeholders).
- 2 weeks feedback loop, bug fixes.

### Pilot (Limited Rollout)
- Deploy to production.
- Invite 50-100 residents from 2-3 neighborhoods.
- Monitor for 2 weeks, collect feedback.
- Fix critical issues, iterate on UX.

### GA (General Availability)
- Public launch, open registration.
- Marketing push, partnerships with local authorities.
- Ongoing support, monitoring, feature requests.
