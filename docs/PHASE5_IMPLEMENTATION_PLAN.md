# Phase 5: Notification Engine — Implementation Notes

## Overview

Phase 5 adds a multi-provider notification engine with asynchronous delivery,
incident alert fanout, SOS emergency-contact dispatch, user preference gating,
rate-limiting, notification history, and background maintenance tasks.

---

## Architecture

```
IncidentStatusTransitionService  ──────┐
SOSAlert creation                      │
                                       ▼
                         NotificationDispatchService
                          ├── _channel_allowed()  ← NotificationPreference
                          ├── _within_rate_limit()
                          ├── Notification.objects.create()
                          └── send_notifications_batch.delay()
                                       │
                         ┌─────────────┴─────────────┐
                    InAppProvider  PushProvider   SMSProvider
                    (mark sent)    (FCM stub)    (Twilio stub)
```

---

## What Was Implemented

### Models (`apps/notifications/models.py`)

| Model | Purpose |
|-------|---------|
| `Notification` | Extended with `retry_count` field |
| `NotificationPreference` | Per-user channel opt-in (push, sms, dashboard) and event-type opt-in (incident alerts, SOS alerts) |
| `NotificationTemplate` | Templated title/body for `incident_verified`, `incident_resolved`, `incident_assigned`, `sos_alert` event types using `str.format_map()` |

### Service layer (`apps/notifications/services.py`)

| Class | Description |
|-------|-------------|
| `BaseProvider` | Abstract adapter with `_mark_sent()` / `_mark_failed()` helpers |
| `InAppProvider` | Dashboard channel — writing the row IS the delivery |
| `PushProvider` | FCM stub — validates active `DeviceToken` exists, marks sent |
| `SMSProvider` | Twilio stub — resolves phone from payload override or recipient, marks sent |
| `NotificationDispatchService.dispatch()` | Creates `Notification` rows for a user list, gating on preferences and rate limit, then queues via `send_notifications_batch.delay()` |
| `NotificationDispatchService.dispatch_incident_alert()` | Fetches neighborhood members, renders template if available, calls `dispatch()` per channel |
| `NotificationDispatchService.dispatch_sos_alert()` | Creates CRITICAL SMS notifications per `EmergencyContact` with `can_receive_sos=True` |

### Celery tasks (`apps/notifications/tasks.py`)

| Task | Schedule | Description |
|------|----------|-------------|
| `send_notifications_batch(ids)` | On demand | Iterates notification IDs, picks provider by channel, delivers or marks failed |
| `retry_failed_notifications()` | Hourly (`crontab(minute=0)`) | Re-queues FAILED notifications < 24h old with `retry_count < 3` |
| `cleanup_old_notifications()` | Daily 3 AM (`crontab(hour=3, minute=0)`) | Soft-deletes notifications older than 90 days |

### Serializers (`apps/notifications/serializers.py`)

| Serializer | Fields |
|------------|--------|
| `NotificationSerializer` | All notification fields (read-only) |
| `NotificationPreferenceSerializer` | Channel toggles + event-type toggles (PATCH-able) |

### Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/me/notifications/` | Paginated list scoped to the authenticated user |
| `PATCH` | `/api/notifications/{id}/read/` | Mark a notification as read |
| `DELETE` | `/api/notifications/{id}/` | Soft-delete a notification |
| `GET` | `/api/me/notification-preferences/` | Retrieve preferences (auto-created on first access) |
| `PATCH` | `/api/me/notification-preferences/` | Update preferences |

### Integration with Phase 3

`IncidentStatusTransitionService.transition()` calls
`NotificationDispatchService.dispatch_incident_alert(incident)` when transitioning
to `VERIFIED`.  The import is deferred (inside the `if` block) to prevent
circular imports between `incidents.services` and `notifications.services`.

### New / modified files

| File | Change |
|------|--------|
| `apps/notifications/models.py` | Added `retry_count`, `NotificationPreference`, `NotificationTemplate` |
| `apps/notifications/migrations/0002_*.py` | Migration for the above |
| `apps/notifications/services.py` | **New** — providers + `NotificationDispatchService` |
| `apps/notifications/tasks.py` | **New** — three Celery tasks |
| `apps/notifications/serializers.py` | Added `NotificationPreferenceSerializer` |
| `apps/notifications/views.py` | **New** — four views |
| `apps/notifications/urls.py` | **New** — URL patterns |
| `apps/notifications/tests/__init__.py` | **New** — package marker |
| `apps/notifications/tests/test_phase5_notification_engine.py` | **New** — 34 tests |
| `apps/incidents/services.py` | Added `dispatch_incident_alert` call on VERIFIED transition |
| `apps/incidents/tests/test_phase3_incidents_api.py` | Patched `send_notifications_batch.delay` in status-transition tests |
| `config/celery.py` | Added two beat schedule entries |
| `config/urls.py` | Included `apps.notifications.urls` |

---

## Design Decisions

### Provider pattern

Providers are stateless objects (no `__init__` arguments) so they can be
instantiated on demand by task workers.  The `PROVIDERS` dict on
`NotificationDispatchService` makes channel → provider lookup O(1) and easy to
extend.

### Preference gating via `get_or_create`

`NotificationPreference` rows are created lazily on first API access, not at
registration.  This avoids a database write on every user signup and keeps the
default (all-enabled) as the assumed state if the row doesn't exist yet.

### Rate limiting

A simple count query against `Notification` (20 per channel per 60-minute
window) is performed before creating each notification row.  This is a
per-worker, in-process check — suitable for the current scale.  A Redis
counter (e.g., `django-ratelimit`) would be appropriate at higher throughput.

### Emergency contacts are not Users

`EmergencyContact` rows have their own `phone_number` field and are not Django
`User` instances.  Rather than creating phantom User rows, the SMS provider
resolves the target phone from `notification.payload["emergency_contact_phone"]`
(set by `dispatch_sos_alert`), falling back to `recipient.phone_number` for
normal SMS notifications.

### Celery task retry

`send_notifications_batch` is declared with `bind=True, max_retries=3` so it
can call `self.retry()` in future if the provider raises a transient error.
Currently the stub providers don't raise network errors, but the wiring is in
place.

---

## Test Coverage

34 tests across:

- `InAppProviderTests` — marks sent
- `PushProviderTests` — no tokens → failed, active token → sent, no recipient → failed
- `SMSProviderTests` — with phone → sent, no phone → failed, payload override → sent
- `DispatchServiceTests` — creates notification, preference gate, rate limit, incident alert fanout, template rendering, no-neighborhood safety, SOS emergency contacts
- `SendNotificationsBatchTaskTests` — delivers dashboard, skips sent, graceful unknown channel
- `RetryFailedNotificationsTaskTests` — requeues recent failures, skips max-retried, skips old
- `CleanupOldNotificationsTaskTests` — soft-deletes old, spares recent
- `NotificationAPITests` — list auth gate, own-only, soft-delete exclusion, mark-as-read, read auth gate, cross-user 404, soft-delete, delete auth gate, cross-user 404
- `NotificationPreferenceAPITests` — GET creates defaults, PATCH updates, auth gate
