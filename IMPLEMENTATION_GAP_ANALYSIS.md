# IMPLEMENTATION_GAP_ANALYSIS.md
**Neighbourhood Watch Zimbabwe — Implementation vs. Documentation Gap Analysis**
*Analysed: 2026-07-18 (supersedes the 2026-06-26 analysis — nearly every gap it documented has since been closed)*

---

## Methodology

Every documented claim was re-traced against the current implementation: settings files, views, serializers, services, frontend pages, and the Docker/Kubernetes stack. Each item below is grounded in specific file evidence. Where the 2026-06-26 analysis flagged something as missing or broken, this document notes the resolution; only items that are still genuinely incomplete are carried forward as open gaps.

---

## 1. Previously Documented Gaps — Now Resolved

These were the headline findings of the June audit. All have been verified fixed in the current codebase:

| # | Item | June finding | Current state |
|---|---|---|---|
| 1 | OTP delivery | Never sent — plaintext code only in DB/response | `OTPService.generate()` dispatches `send_otp_email` (Celery task, `apps/accounts/tasks.py`), which calls `send_mail()` with retry-on-failure. `debug_code` in the response is gated behind `OTP_EXPOSE_DEBUG_CODES` (defaults to `DEBUG`), not exposed unconditionally. |
| 2 | File storage (MinIO/S3) | Configured, never wired | `base.py` wires `STORAGES["default"]` to `S3Boto3Storage` pointed at MinIO when `USE_S3_STORAGE=True`, with presigned URLs (1hr expiry). `docker-compose.yml` runs a `minio` service. |
| 3 | Celery tasks | Worker/tasks missing entirely | `config/celery.py` defines a Celery app with a 4-job beat schedule (OTP cleanup, notification retry, notification cleanup, daily analytics). `@shared_task` functions exist in `accounts/tasks.py`, `notifications/tasks.py`, `analytics/tasks.py`. `docker-compose.yml` has dedicated `celery` and `celery-beat` services. |
| 4 | Notification engine | Models only, no dispatch | `apps/notifications/services.py` implements a full `NotificationDispatchService` with provider adapters; `views.py`/`urls.py` expose an inbox (list/read/delete/preferences). In-app delivery is fully live. (Push/SMS providers remain simulated — see §3 below, carried forward as an open item.) |
| 5 | Neighborhoods API | No endpoints | `apps/neighborhoods/views.py` + `urls.py` now expose full CRUD via a DRF router, wired into `config/urls.py`. |
| 6 | SOS module | No endpoints | `apps/sos/views.py` + `urls.py` expose the full alert lifecycle: create, ping, resolve, cancel, and a neighborhood-scoped `active` list for coordinators/police/admins. |
| 7 | Analytics | No logic | A Celery task (`generate_daily_snapshots`) populates `AnalyticsSnapshot` on a schedule, and a read-only list endpoint exposes it. (Still no write API or tests — carried forward as an open item, narrower in scope than before.) |
| 8 | Offline sync API | No endpoint | `apps/sync/views.py` exposes `sync/queue/` (GET) and `sync/push/` (POST), backed by `services.py` conflict/idempotency logic. |
| 9 | Kubernetes manifests | Directory didn't exist | `k8s/` now contains 9 manifests: namespace, configmap, secrets, postgres-statefulset, redis-deployment, api-deployment, celery-deployment, nginx-ingress, hpa. |
| 10 | Frontend OTP verification step | Missing | `register.jsx` now has a full OTP entry step post-registration, calling `verifyOtp`/`requestOtp` against the real API before navigating to `/profile`. |
| 11 | Frontend profile page | Read-only | Profile editing is live and calls the `PATCH /api/users/me` endpoint. |
| 12 | Rate limiting | In-memory only | `base.py` now configures `CACHES["default"]` via `django.core.cache.backends.redis.RedisCache`, giving DRF's `SimpleRateThrottle` a shared, distributed backend across workers. |
| 13 | Logout token blacklist | Never called from frontend | `App.jsx`'s `handleLogout` now calls `logout(refresh)` (fire-and-forget) alongside clearing local storage. |
| 14 | CORS unconfigured in dev | Blocked local frontend | `local.py` now overrides `CORS_ALLOWED_ORIGINS` for `localhost:5173`. |
| 15 | JWT env var name mismatch | `.env.example` documented a variable Django never read | `base.py` now reads `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, matching `.env.example`. |
| 16 | Register page crash (`IdCard`) | `ReferenceError` on render, blocking all registration | Current `register.jsx` imports only icons it uses (`Mail, Lock, Phone, CreditCard, MapPin, User, AlertCircle, KeyRound`); no `IdCard` reference exists. |
| 17 | Nginx serves media without auth | Any UUID guess could fetch evidence files | `infra/nginx/default.conf` now marks `/protected-media/` `internal;`, reachable only via Django's `X-Accel-Redirect`, itself gated by `ProtectedMediaView`'s `IsAuthenticated` check. |
| 18 | `ProtectedRoute` shows HomePage instead of redirecting | Confusing UX, leaked nav chrome | `App.jsx`'s `ProtectedRoute` now renders `<Navigate to="/login" replace />`. |
| 19 | Four stub pages (incidents, incident-detail, verification, coordinator) | Permanent spinners | All four now make real API calls (list/detail/submit/approve-reject respectively). |
| 20 | `db.sqlite3` / `media/` committed | Risk of leaking dev data | `.gitignore` now excludes `*.sqlite3` and `media/`. |
| 21 | No CI/CD | No `.github/workflows/` | Three workflows now exist: `backend-ci.yml`, `frontend-ci.yml`, `docker-build.yml`. |

---

## 2. Gaps Still Open

### 2.1 Push & SMS Notification Providers Are Simulated

**Location**: `backend/apps/notifications/services.py`

`PushProvider` and `SMSProvider` validate that a device token / phone number exists and mark the notification `sent`, but neither makes an actual external API call — the docstrings explicitly describe this as the production integration point ("Production: call FCM API...", "Production: call Twilio client..."). `InAppProvider` is fully functional since the in-app inbox IS the delivery mechanism, so this only affects push and SMS channels. Consequence: a user who has push/SMS as their only notification preference will see the `Notification` record marked `sent` without actually receiving anything on their device.

**Related**: SMS is a defined OTP channel (`OTPChallenge.Channel.SMS`) but `OTPService.generate()` only wires a delivery task for the EMAIL channel — an SMS OTP request would create a challenge with no corresponding send.

---

### 2.2 `HasRoleCapability` Permission Class Is Defined but Unused

**Location**: `backend/apps/accounts/permissions.py`

This granular, permission-code-based authorization class exists alongside `HasAnyRole`, but no view in the codebase declares `required_permissions`. All current RBAC enforcement uses `HasAnyRole` (role-code comparison) or hardcoded role checks. The seeded `Permission`/`RolePermission` records (`seed_roles` management command) have no runtime effect. This is a much narrower version of the June finding — the RBAC system as a whole is now enforced (previously it had no effect anywhere) — but the fine-grained permission table remains dormant.

---

### 2.3 Analytics App Has No Write API and No Tests

**Location**: `backend/apps/analytics/`

Snapshot generation runs via the Celery beat schedule (`generate_daily_snapshots`), and a read-only list endpoint exposes the results. There is no endpoint to trigger an on-demand snapshot, and no test file exists under `backend/apps/analytics/tests/` (the directory doesn't appear to exist at all) — this is the one backend app with zero automated coverage.

---

### 2.4 Audit App Has No Exposed Read API and No Tests

**Location**: `backend/apps/audit/`

`create_audit_log` and `snapshot_model` are called from other apps (accounts, incidents) to write immutable log entries, but there's no endpoint to read them back — an administrator investigating an incident has no API-level way to pull the audit trail, only direct DB/admin access. No dedicated test file exists for this app either.

---

### 2.5 Frontend Has No Automated Test Suite

**Location**: `frontend/`

`package.json` declares no test runner (no vitest, no jest, no `test` script). No `__tests__` directories or `*.test.jsx`/`*.spec.jsx` files exist anywhere under `frontend/src`. All frontend verification currently happens via manual testing and the production build (`vite build`), which catches syntax/import errors but not behavioral regressions.

---

### 2.6 Flutter Mobile App Not Started

**Location**: N/A — directory doesn't exist

No `mobile/` or `flutter/` directory exists anywhere in the repository. This was flagged as a Phase 6 deliverable in the June analysis and remains fully unstarted; it's a separate, larger effort than the other items in this document (the web/API surface it would consume is otherwise ready).

---

## Summary Table

| Category | June 2026 | July 2026 |
|---|---|---|
| Features documented but not implemented | 11 | 1 (mobile app only) |
| Partially implemented features | 5 | 2 (notification providers, analytics write API) |
| Broken integrations | 8 | 0 |
| Security issues | 6 | 0 (all resolved: distributed rate limiting, auth-gated media, token blacklist on logout) |
| Missing test coverage | not tracked separately | 3 (analytics, audit, frontend) |
| RBAC gaps | 1 (no effect anywhere) | 1 (narrower: one permission class unused, enforcement otherwise works) |

---

*End of gap analysis — regenerated 2026-07-18*
