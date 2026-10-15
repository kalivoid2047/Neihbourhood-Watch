# PROJECT_AUDIT.md
**Neighbourhood Watch Zimbabwe — Full Codebase Audit**
*Audited: 2026-07-18 (supersedes the 2026-06-26 audit, which described an earlier ~50%-complete state)*

---

## Executive Summary

Neighbourhood Watch Zimbabwe is a community-driven security and emergency response platform targeting Zimbabwean neighborhoods. Since the previous audit, the project has moved from "backend core only, frontend shell" to a **substantially complete full-stack application**: every backend app now has models, serializers, views, and URLs wired up; every frontend page makes real API calls instead of rendering a stub; Celery workers, MinIO storage, and Redis caching are all configured and running; Kubernetes manifests and a CI/CD pipeline exist.

253 backend tests pass, flake8 is clean, and the frontend builds without errors. The remaining gaps are narrower and more specific than before: two backend apps (analytics, audit) lack test coverage, push/SMS notification providers are scaffolded but not wired to real FCM/Twilio APIs, one RBAC permission class is defined but unused, and the frontend has no automated test suite. The Flutter mobile app remains unstarted.

**Overall Estimated Completion: ~90% of the documented Phase 1–6 scope** (excluding the mobile app, which is a separate, unstarted deliverable).

---

## Current Architecture

### Stack Overview

| Layer | Technology |
|---|---|
| Frontend | React 18, React Router v6, Tailwind CSS 3, Vite, Axios |
| Backend | Django 5.2, Django REST Framework, SimpleJWT |
| Database (dev) | SQLite (`config.settings.local` / `config.settings.test`) |
| Database (prod) | PostgreSQL 16 + PostGIS |
| Cache / Queue Broker | Redis (`django.core.cache.backends.redis.RedisCache`, live in `base.py`) |
| Task Queue | Celery — worker + beat, both running as Docker services with a 4-job schedule |
| Real-time | Django Channels over `channels_redis`, WebSocket consumers in `apps/core/consumers.py` |
| File Storage | MinIO (S3-compatible) via `django-storages` when `USE_S3_STORAGE=True`; local `media/` otherwise |
| Reverse Proxy | Nginx, with `/protected-media/` marked `internal` and gated by Django auth |
| Containerization | Docker Compose (dev/staging) + Kubernetes manifests (`k8s/`) |
| CI/CD | GitHub Actions — `backend-ci.yml`, `frontend-ci.yml`, `docker-build.yml` |

### Request Flow (Backend)

```
HTTP → Nginx → Gunicorn → Django Middleware (CORS, auth) →
URL Router → DRF Auth (JWT) → DRF Permissions (RBAC) →
DRF Throttle (Redis-backed) → Serializer → View → Service Layer → ORM → DB
```

Async work (OTP email delivery, notification dispatch/retry/cleanup, daily analytics snapshots) is offloaded to Celery via a beat schedule rather than running inline in the request/response cycle.

---

## Folder Map

```
Neighbourhood Watch/
├── backend/
│   ├── config/
│   │   ├── celery.py            # Celery app + 4-job beat schedule
│   │   ├── settings/
│   │   │   ├── base.py          # Shared settings — Redis cache, MinIO/S3, Channels
│   │   │   ├── local.py         # SQLite dev, CORS overridden for localhost:5173
│   │   │   ├── test.py          # SQLite test, in-memory cache
│   │   │   └── production.py    # PostgreSQL + PostGIS
│   │   └── urls.py              # Root URL config — all 8 apps wired in
│   ├── apps/
│   │   ├── core/                # ✅ FULL: base model, health/metrics/schema, protected media, WebSocket consumers
│   │   ├── accounts/             # ✅ FULL: auth, OTP (email via Celery), verification, RBAC, emergency contacts
│   │   ├── incidents/           # ✅ FULL: incident CRUD, media, status workflow, geospatial (PostGIS), sync/checksum
│   │   ├── neighborhoods/       # ✅ FULL: CRUD via router, membership, permissions
│   │   ├── notifications/       # ✅ FULL dispatch engine + inbox; ⚠️ push/SMS providers are simulated, not wired to FCM/Twilio
│   │   ├── sos/                 # ✅ FULL: alert lifecycle, location pings, neighborhood-scoped visibility
│   │   ├── audit/               # ✅ Service layer used by other apps; no public read endpoint; ⚠️ no tests
│   │   ├── analytics/           # ⚠️ PARTIAL: read-only list endpoint + Celery snapshot generation; no write API; no tests
│   │   └── sync/                # ✅ FULL: offline sync queue + push endpoint
│   ├── manage.py
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router (9 routes, ProtectedRoute redirects to /login)
│   │   ├── api.js                # Axios client with JWT interceptors
│   │   ├── pages/
│   │   │   ├── home.jsx          # ✅ Landing page
│   │   │   ├── login.jsx         # ✅ Functional login form
│   │   │   ├── register.jsx      # ✅ Functional registration + OTP verification step
│   │   │   ├── profile.jsx       # ✅ View/edit profile
│   │   │   ├── incidents.jsx     # ✅ Incident list/map, calls real API
│   │   │   ├── incident-detail.jsx # ✅ Full detail view, media, status timeline
│   │   │   ├── verification.jsx  # ✅ Resident verification request submission
│   │   │   ├── coordinator.jsx   # ✅ Coordinator queue, approve/reject calls real API
│   │   │   └── notifications.jsx # ✅ Inbox — fetch/read/delete, calls real API
│   │   ├── components/
│   │   │   ├── ui.jsx             # ✅ Design system (Button, Card, Badge, Modal…)
│   │   │   ├── layout.jsx         # ✅ Header, Footer, PageHeader, PageContent
│   │   │   └── IncidentMap.jsx    # ✅ Leaflet map integration
│   │   └── styles/globals.css
│   ├── package.json              # No test runner configured (no vitest/jest)
│   └── vite.config.js
├── infra/
│   ├── docker/backend.Dockerfile
│   └── nginx/default.conf        # /protected-media/ marked internal, security headers set
├── k8s/                          # ✅ Present: namespace, configmap, secrets, postgres, redis, api, celery, ingress, hpa
├── .github/workflows/            # ✅ backend-ci.yml, frontend-ci.yml, docker-build.yml
├── docs/
├── docker-compose.yml            # api, postgres, redis, minio, celery, celery-beat, nginx
└── requirements/                 # Split requirement files (base/dev/prod)
```

---

## Database Schema

All domain models extend `UUIDTimeStampedModel` (abstract base) which provides:
- `id` — UUID primary key
- `created_at`, `updated_at`, `last_modified_at` — auto timestamps
- `deleted_at` — soft deletion (non-null = deleted)
- `objects` — manager that filters out deleted rows by default
- `all_objects` — manager that returns everything

Schema is unchanged in shape from the previous audit (same tables across accounts, neighborhoods, incidents, notifications, sos, audit, analytics, sync) — what has changed is that nearly every table is now reachable through a real API endpoint instead of sitting dormant behind a bare model.

---

## API Inventory

### System
| Method | Path | Description |
|---|---|---|
| GET | `/api/` | API root / version info |
| GET | `/api/health/` | Health check |
| GET | `/api/metrics/` | Metrics |
| GET | `/api/schema/` | OpenAPI schema |
| GET | `/api/media/<path>` | Protected media (auth-gated, `X-Accel-Redirect` via nginx `internal`) |
| POST | `/api/token/`, `/api/token/refresh/` | JWT obtain/refresh (SimpleJWT direct) |

### Authentication (`/api/auth/...`)
| Method | Path | Description |
|---|---|---|
| POST | `auth/register` | Register new user + trigger OTP |
| POST | `auth/login` | Login with email/password → JWT |
| POST | `auth/refresh` | Refresh access token |
| POST | `auth/logout` | Blacklist refresh token |
| POST | `auth/request-otp` | Re-send OTP |
| POST | `auth/verify-otp` | Confirm OTP code |
| POST | `auth/forgot-password` | Initiate password reset |
| POST | `auth/reset-password` | Complete password reset with OTP |

### Users & Verification
| Method | Path | Description |
|---|---|---|
| GET/PATCH | `users/me` | Get/update current user profile |
| POST | `verification-requests` | Resident submits verification request |
| GET | `coordinator/verification-requests` | List pending requests (`HasAnyRole`: coordinator/admin) |
| POST | `coordinator/verification-requests/{id}/approve` | Approve resident |
| POST | `coordinator/verification-requests/{id}/reject` | Reject resident |
| GET/POST | `me/emergency-contacts` | List/create emergency contacts |
| GET/PATCH/DELETE | `me/emergency-contacts/{id}` | Manage a single contact |

### Incidents (`/api/incidents/...`, router-based)
| Method | Path | Description |
|---|---|---|
| GET/POST | `incidents/` | List (role-filtered) / create |
| GET/PATCH/DELETE | `incidents/{id}/` | Retrieve / update / soft-delete |
| POST | `incidents/{id}/verify/` | Coordinator verifies incident |
| POST | `incidents/{id}/transition_status/` | Move through status workflow |
| POST | `incidents/{id}/assign/` | Assign incident to responder |
| GET | `incidents/{id}/media/` | List incident media |
| POST | `incidents/{id}/upload_media/` | Upload image/video/audio |
| GET/DELETE | `media/{id}/` | Retrieve or delete media file |
| GET | `incidents/heatmap/` | Geospatial heatmap cells (PostGIS) |

### Neighborhoods (`/api/neighborhoods/...`, router-based)
Full CRUD, plus membership management endpoints.

### SOS (`/api/sos/...`, router-based)
| Method | Path | Description |
|---|---|---|
| GET/POST | `sos/` | List own alerts / create alert (dispatches emergency contacts) |
| POST | `sos/{id}/ping/` | Add location ping |
| POST | `sos/{id}/resolve/` | Resolve alert |
| POST | `sos/{id}/cancel/` | Cancel alert |
| GET | `sos/active/` | Active alerts, neighborhood-scoped (coordinator/police/admin only) |

### Notifications
| Method | Path | Description |
|---|---|---|
| GET | `me/notifications/` | Inbox |
| POST | `notifications/{id}/read/` | Mark read |
| DELETE | `notifications/{id}/` | Delete |
| GET/PATCH | `me/notification-preferences/` | Channel preferences |

### Sync & Analytics
| Method | Path | Description |
|---|---|---|
| GET | `sync/queue/` | Offline sync queue |
| POST | `sync/push/` | Push delta changes |
| GET | `analytics/` | Read-only analytics snapshots (write side is Celery-only) |

---

## Authentication Flow

1. **Register**: `POST /api/auth/register` → creates User + OTPChallenge → Celery task `send_otp_email` dispatches a real email via `send_mail()` with retry-on-failure (3 retries, 30s delay). `debug_code` is only included in the response when `OTP_EXPOSE_DEBUG_CODES` (defaults to `DEBUG`) is true.
2. **Verify OTP**: `POST /api/auth/verify-otp` → validates hashed code, sets `user.otp_verified_at`.
3. **Login**: `POST /api/auth/login` → returns `{access, refresh}` JWT pair.
4. **Subsequent Requests**: `Authorization: Bearer <access_token>` header.
5. **Token Refresh**: `POST /api/auth/refresh`.
6. **Logout**: `POST /api/auth/logout` → blacklists refresh token server-side; the frontend's `handleLogout` calls this (fire-and-forget) in addition to clearing local storage.

**Note**: SMS is a defined OTP channel on the model (`OTPChallenge.Channel`) but only the EMAIL channel currently has a delivery task wired into `OTPService.generate()`.

---

## Current Completion Percentage

| Area | Status | % Complete |
|---|---|---|
| Backend — Foundation (models, migrations, base, Channels, protected media) | Done | 100% |
| Backend — Auth & User Management (incl. OTP email delivery) | Done | 100% |
| Backend — Incident CRUD + Media + RBAC + Geospatial | Done | 100% |
| Backend — Neighborhoods API | Done | 100% |
| Backend — SOS API | Done | 100% |
| Backend — Notifications (dispatch engine, inbox, in-app delivery) | Done, providers stubbed | 85% |
| Backend — Analytics | Read-only, no tests | 55% |
| Backend — Offline Sync API | Done | 100% |
| Backend — Celery (workers, beat, 4 scheduled jobs) | Done | 100% |
| Frontend — Auth pages (login, register incl. OTP step) | Done | 100% |
| Frontend — Profile page | Done | 100% |
| Frontend — Home page | Done | 100% |
| Frontend — Design system / component library | Done | 100% |
| Frontend — Incidents list + detail pages | Done | 100% |
| Frontend — Coordinator queue page | Done | 100% |
| Frontend — Verification page | Done | 100% |
| Frontend — Notifications inbox | Done | 100% |
| Infrastructure — Docker Compose (7 services incl. celery/celery-beat) | Done | 100% |
| Infrastructure — Kubernetes manifests | Done (9 manifests) | 100% |
| Infrastructure — CI/CD (GitHub Actions) | Done (3 workflows) | 100% |
| Testing — Backend | 253/253 passing | 90% (analytics + audit apps have zero test files) |
| Testing — Frontend | None configured | 0% |
| Mobile — Flutter app | Not started | 0% |

**Overall Estimated Completion: ~90%** of Phase 1–6 web/API scope; mobile is a separate 0%-started deliverable.

---

## Missing / Incomplete Items

1. **Push & SMS notification providers are simulated** — `PushProvider` and `SMSProvider` in `apps/notifications/services.py` validate that a device token / phone number exists and mark the notification `sent`, but contain no actual FCM or Twilio API call (docstrings explicitly say "Production: call FCM API...' / 'Production: call Twilio client..."). In-app notifications are fully live (the dashboard inbox IS the delivery channel). SMS OTP delivery is likewise unwired (see Authentication Flow above).
2. **`HasRoleCapability` permission class is unused** — defined in `apps/accounts/permissions.py` for granular, permission-code-based authorization, but no view declares `required_permissions`. All current RBAC enforcement runs through the coarser `HasAnyRole` class (role-code comparison) or hardcoded role checks. The seeded `Permission`/`RolePermission` records have no runtime effect yet.
3. **Analytics app has no write API and no tests** — snapshot generation is Celery-only (`generate_daily_snapshots`, part of the beat schedule); there's a read-only list endpoint but nothing to trigger a snapshot on demand via the API, and no test file exists under `backend/apps/analytics/`.
4. **Audit app has no exposed read API and no tests** — `create_audit_log`/`snapshot_model` are used internally by other apps, but there's no `/api/audit/` endpoint for reviewing the log, and no dedicated test file.
5. **Frontend has zero automated tests** — no vitest/jest config in `package.json`, no `__tests__` directories, no `*.test.jsx` files anywhere under `frontend/src`.
6. **Flutter mobile app not started** — no `mobile/` or `flutter/` directory exists anywhere in the repo.

---

## Recommended Implementation Order

### Tier 1 — Close remaining gaps in the web/API scope
1. Wire `PushProvider` to a real FCM client and `SMSProvider` to Twilio (or another SMS gateway); add an SMS-channel OTP delivery task to match the email path.
2. Add test coverage for `apps/analytics` and `apps/audit`.
3. Decide whether `HasRoleCapability` should be adopted (wire `required_permissions` onto views that need granular control) or removed if `HasAnyRole` is judged sufficient — leaving it defined-but-dead invites drift.
4. Set up Vitest + React Testing Library for the frontend; cover auth flows, incidents list, and the coordinator/verification flows at minimum.

### Tier 2 — Operational hardening
5. Consider exposing a minimal audit-log read endpoint (admin-only) for operational visibility.
6. Consider an on-demand analytics snapshot trigger for admins, in addition to the daily Celery job.

### Tier 3 — Phase 6+ (future, unstarted)
7. **Flutter Mobile App** — new `mobile/` directory with screens for reporting, SOS, and notifications, consuming the existing REST/WebSocket API.

---

*End of audit — regenerated 2026-07-18*
