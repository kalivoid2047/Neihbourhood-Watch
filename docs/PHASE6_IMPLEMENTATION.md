# Phase 6 Implementation

Real-time WebSocket updates, Maps, Offline Sync API, and Analytics.

---

## Backend

### WebSocket (Django Channels 4)

| File | Purpose |
|------|---------|
| `apps/core/consumers.py` | `IncidentConsumer`, `NotificationConsumer` — JWT auth via `?token=` query param |
| `apps/core/routing.py` | URL patterns: `ws/incidents/<uuid>/`, `ws/notifications/` |
| `apps/core/broadcasting.py` | Safe sync→async helpers: `broadcast_incident_update`, `broadcast_notification` |
| `config/asgi.py` | `ProtocolTypeRouter` with `AllowedHostsOriginValidator` |
| `config/settings/test.py` | `InMemoryChannelLayer` override for tests |

**Auth strategy**: JWT access token passed as `?token=<jwt>` in the WebSocket URL. Headers cannot be set on WS upgrade requests in browsers.

**Broadcast hooks**:
- `apps/incidents/views.py` → `verify` and `transition_status` actions broadcast after service calls
- `apps/notifications/tasks.py` → `send_notifications_batch` broadcasts DASHBOARD notifications on delivery

### Sync API

| File | Purpose |
|------|---------|
| `apps/sync/serializers.py` | `SyncPushSerializer` (batch of items), `SyncQueueSerializer` |
| `apps/sync/services.py` | `SyncPushService.push(user, items)` — idempotency, conflict detection, dispatch |
| `apps/sync/views.py` | `GET /api/sync/queue/`, `POST /api/sync/push/` |
| `apps/sync/urls.py` | URL routing |

**Conflict detection**: `UPDATE` operations compare the client's `local_modified_at` against the server's `last_modified_at`. If the server record is newer, the result is `conflict`.

**Idempotency**: duplicate `idempotency_key` submissions return the existing `SyncQueue` record without re-applying.

### Analytics API

| File | Purpose |
|------|---------|
| `apps/analytics/serializers.py` | `AnalyticsSnapshotSerializer` (read-only) |
| `apps/analytics/views.py` | `GET /api/analytics/` — filterable by `neighborhood` and `snapshot_type` |
| `apps/analytics/tasks.py` | Celery task `generate_daily_snapshots` — calls `IncidentGeospatialService.neighborhood_risk_summary` per active neighborhood |
| `config/celery.py` | Beat schedule: daily at 01:00 |

---

## Frontend

### New files

| File | Purpose |
|------|---------|
| `src/hooks/useWebSocket.js` | Generic auto-reconnecting WebSocket hook |
| `src/components/IncidentMap.jsx` | Leaflet map with severity-colored markers |
| `src/pages/notifications.jsx` | Notification list with mark-as-read and delete |

### Modified files

| File | Change |
|------|--------|
| `src/api.js` | Added notification API functions, `openWebSocket`, `openIncidentSocket`, `openNotificationSocket` |
| `src/pages/incident-detail.jsx` | Live updates via `useWebSocket` + live/offline indicator |
| `src/pages/incidents.jsx` | List/Map toggle; `IncidentMap` rendered in map view |
| `src/components/layout.jsx` | `NotificationBell` component in header (unread count + WS subscription) |
| `src/App.jsx` | `/notifications` route added |
| `package.json` | Added `leaflet ^1.9.4`, `react-leaflet ^4.2.1` |

### WebSocket connection flow

```
Browser                      Django Channels
  │── WS connect ─────────────────────────────►│
  │   /ws/incidents/<id>/?token=<jwt>           │
  │                                             ├─ _authenticate() decodes JWT
  │                                             ├─ group_add(f"incident_{id}")
  │◄─ 101 Switching Protocols ─────────────────│
  │                                             │
  │   (another request verifies incident)       │
  │                                             ├─ broadcast_incident_update(incident)
  │                                             │   layer.group_send("incident_{id}", ...)
  │◄─ {"type":"incident_updated", ...} ────────│
```

---

## Tests

| Suite | Location | Count |
|-------|----------|-------|
| WS consumer auth | `apps/core/tests/test_phase6_consumers.py` | 7 |
| Broadcasting helpers | `apps/core/tests/test_phase6_consumers.py` | 5 |
| Sync API | `apps/sync/tests/test_phase6_sync.py` | 16 |
| Analytics API | `apps/sync/tests/test_phase6_sync.py` | 4 |
| **Total Phase 6** | | **32** |
| **Grand total** | | **198** |

**Key testing notes**:
- WebSocket tests use `TransactionTestCase` so committed rows are visible to `database_sync_to_async` thread pool workers.
- Tests bypass `AllowedHostsOriginValidator` by constructing `URLRouter(websocket_urlpatterns)` directly — the validator rejects connections without an `Origin` header, which `WebsocketCommunicator` doesn't set.
- `asyncio.run()` wraps each test coroutine so each test gets an isolated event loop; channel layer queues don't bleed between tests.

---

## API Endpoints Added

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `WS` | `/ws/incidents/<uuid>/` | JWT query | Live incident updates |
| `WS` | `/ws/notifications/` | JWT query | Live notification push |
| `GET` | `/api/sync/queue/` | Bearer | List user's sync queue (`?status=`) |
| `POST` | `/api/sync/push/` | Bearer | Push offline mutations batch |
| `GET` | `/api/analytics/` | Bearer | List analytics snapshots |

## Static Analysis

```
$ python manage.py check --settings=config.settings.local
System check identified no issues (0 silenced).
```

## Remaining Known Issues

1. **`react-leaflet` / `leaflet` not yet installed** — run `npm install` in `frontend/` before the map renders. `package.json` has been updated with the dependency entries.
2. **Leaflet CSS not imported globally** — add `import 'leaflet/dist/leaflet.css'` to `src/main.jsx` after installing the package, otherwise map tiles render without styles.
3. **No Flutter mobile app** — Phase 6 roadmap included Flutter; that remains out of scope. The backend sync/WS APIs are protocol-compatible with a future Flutter client.

All API endpoints verified present and matching (`/api/notifications/<id>/read/`, `DELETE /api/notifications/<id>/`, `AnalyticsSnapshot.source_version`).
