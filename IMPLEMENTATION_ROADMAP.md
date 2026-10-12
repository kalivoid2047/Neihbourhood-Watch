# IMPLEMENTATION_ROADMAP.md
**Neighbourhood Watch Zimbabwe — Phased Implementation Roadmap**
*Generated: 2026-06-26 | Based on: PROJECT_AUDIT.md + IMPLEMENTATION_GAP_ANALYSIS.md*

---

## Reading This Document

Phases are ordered by **dependency and risk**, not by feature desirability. Phases 1–3 are
non-negotiable prerequisites: the app is currently broken for new users and misconfigured for
any real deployment. Phases 4–6 build the remaining backend feature surface. Phases 7–8
complete the client experience and production hardening.

Complexity ratings use T-shirt sizing relative to this codebase:
- **XS** — < 1 hour, single file
- **S** — half-day, 2–4 files
- **M** — 1–3 days, a full app module
- **L** — 1–2 weeks, cross-cutting or new app module
- **XL** — 2–4 weeks, new technology integration

---

## Phase 1 — Critical Defect Fixes
**Objective**: Restore the minimum viable state where a user can open the app, register, log in, and log out without hitting a runtime crash or a silently broken flow. Nothing in later phases is worth building on top of the current broken baseline.

**Target completion**: 1–2 days

---

### 1.1 Fix Registration Page Crash (`IdCard` Import)

**Problem**: `register.jsx` uses `<IdCard>` but imports `FileText` instead. Every user who navigates to `/register` gets a JavaScript `ReferenceError` and a blank screen.

**Files affected**:
- `frontend/src/pages/register.jsx` — line 3 (import), line 113 (usage)

**Change**:
```js
// Before
import { Mail, Lock, Phone, FileText, MapPin, User, AlertCircle } from 'lucide-react';

// After
import { Mail, Lock, Phone, IdCard, MapPin, User, AlertCircle } from 'lucide-react';
```

**Complexity**: XS
**Dependencies**: None
**Testing required**: Render `/register` in browser; confirm National ID field shows the card icon, not a crash. Verify form submission still works end-to-end.
**Deployment impact**: Frontend rebuild only. No backend change.

---

### 1.2 Fix `ProtectedRoute` — Redirect to `/login` Instead of Rendering `<HomePage>`

**Problem**: Unauthenticated access to `/incidents`, `/profile`, `/coordinator`, `/verify` renders the full home page inside the authenticated layout shell instead of redirecting.

**Files affected**:
- `frontend/src/App.jsx` — lines 79–84

**Change**:
```jsx
// Before
const ProtectedRoute = ({ children }) => {
  if (!auth.user) {
    return <HomePage />;
  }
  return children;
};

// After
import { Navigate } from 'react-router-dom';

const ProtectedRoute = ({ children }) => {
  if (!auth.user) {
    return <Navigate to="/login" replace />;
  }
  return children;
};
```

**Complexity**: XS
**Dependencies**: None
**Testing required**: Visit `/incidents` while logged out; confirm redirect to `/login`. Confirm back-navigation after login works.
**Deployment impact**: Frontend rebuild only.

---

### 1.3 Fix Logout — Blacklist the Refresh Token on the Server

**Problem**: `handleLogout` in `App.jsx` only clears `localStorage`. The refresh token stays valid on the server for 7 days, making logout a no-op from a security standpoint.

**Files affected**:
- `frontend/src/App.jsx` — `handleLogout` function (lines 48–52)

**Change**:
```jsx
// Before
const handleLogout = () => {
  clearTokens();
  auth.setUser(null);
  auth.navigate('/');
};

// After
import { logout, getRefreshToken, clearTokens } from './api';

const handleLogout = async () => {
  const refresh = getRefreshToken();
  clearTokens();          // clear locally first so UI feels instant
  auth.setUser(null);
  auth.navigate('/');
  if (refresh) {
    try { await logout(refresh); } catch { /* token already expired or network error */ }
  }
};
```

**Complexity**: XS
**Dependencies**: `logout()` already implemented in `api.js`
**Testing required**: Log in, capture the refresh token, log out, attempt `POST /api/auth/refresh` with the captured token — expect 401. Confirm logout still works if the server is unreachable (network error must not block the UI logout).
**Deployment impact**: Frontend rebuild only.

---

### 1.4 Fix CORS for Local Development

**Problem**: `CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")` defaults to `[]` in `local.py`, blocking all cross-origin requests from the Vite dev server (`localhost:5173`).

**Files affected**:
- `backend/config/settings/local.py`

**Change**:
```python
# Append to local.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
```

**Complexity**: XS
**Dependencies**: None
**Testing required**: With backend on port 8000 and frontend on port 5173, confirm login API call succeeds (no CORS error in browser console).
**Deployment impact**: Development environment only. Production uses the `CORS_ALLOWED_ORIGINS` env var already.

---

### 1.5 Fix JWT Env Variable Name Mismatch

**Problem**: `base.py` reads `JWT_ACCESS_TOKEN_MINUTES` (default 15 min) but `.env.example` documents `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60`. README says tokens last 1 hour. Copying `.env.example` to `.env` has no effect on token lifetime.

**Files affected**:
- `.env.example` — update the env var names to match what `base.py` actually reads
- `backend/config/settings/base.py` — optionally rename the env var to the more descriptive name (coordinate both changes)

**Change** (update `.env.example` to match `base.py`, and change `base.py` to use the clearer name):
```python
# base.py
"ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 60)),
"REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)),
```
```bash
# .env.example
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Complexity**: XS
**Dependencies**: None
**Testing required**: Set `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=5` in `.env`, start server, confirm access token expires in 5 minutes. Update README to remove the hardcoded "1 hour" claim.
**Deployment impact**: Any existing `.env` files referencing the old key need updating. Low risk since the default is being changed simultaneously.

---

### 1.6 Fix Nginx Upload Size Limit

**Problem**: `client_max_body_size 50m` in nginx rejects uploads between 50MB and 100MB with HTTP 413 before Django sees the request. API and docs both allow 100MB.

**Files affected**:
- `infra/nginx/default.conf` — line 7

**Change**:
```nginx
client_max_body_size 110m;  # 10m buffer above the 100MB Django limit
```

**Complexity**: XS
**Dependencies**: None
**Testing required**: Upload a 75MB file via the API; confirm 201 Created, not 413.
**Deployment impact**: Nginx container restart required. No application code change.

---

### Phase 1 Summary

| Item | Complexity | Files | Risk |
|---|---|---|---|
| 1.1 IdCard import fix | XS | 1 | Zero |
| 1.2 ProtectedRoute redirect | XS | 1 | Zero |
| 1.3 Logout blacklist | XS | 1 | Low |
| 1.4 CORS local dev | XS | 1 | Zero |
| 1.5 JWT env var name | XS | 2 | Low |
| 1.6 Nginx upload limit | XS | 1 | Zero |

**Total estimated effort**: 2–4 hours
**Gate to Phase 2**: All 6 items must be complete. The registration page crash (1.1) blocks all new user testing.

---

## Phase 2 — Frontend Core Pages
**Objective**: Wire the four stub pages to their already-implemented backend APIs. By the end of this phase, a user can: register, verify their phone, log in, see their incidents, report a new incident, view incident details, submit a verification request, and coordinators can approve/reject residents. The backend for all of this already exists — this phase is entirely frontend work.

**Target completion**: 1–2 weeks

---

### 2.1 OTP Verification Screen (Post-Registration)

**Problem**: Registration succeeds and returns an OTP challenge, but the frontend navigates to `/profile` without ever asking the user for the code.

**Files affected**:
- `frontend/src/pages/register.jsx` — add post-submission OTP step
- `frontend/src/api.js` — add `verifyOtp(identifier, code)` function
- `frontend/src/App.jsx` — optionally add `/verify-otp` route or handle inline

**Implementation**:
After a successful `register()` call, show an inline form asking for the 6-digit code. On submit, call `POST /api/auth/verify-otp` with `{ identifier: email, purpose: "registration", code }`. On success, navigate to `/profile`. Include a "Resend code" link calling `POST /api/auth/request-otp`.

**Complexity**: S
**Dependencies**: Phase 1.1 (register page must render first)
**Testing required**:
- Register; confirm OTP step appears
- Enter wrong code; confirm error message
- Enter correct code (from `debug_code` in dev response); confirm navigation to `/profile`
- Test "Resend code" flow
**Deployment impact**: Frontend only.

---

### 2.2 Incidents List Page

**Problem**: `incidents.jsx` is a spinner. The backend `GET /api/incidents/` returns paginated, role-filtered incidents.

**Files affected**:
- `frontend/src/pages/incidents.jsx` — full implementation
- `frontend/src/api.js` — add `fetchIncidents(page)`, `fetchIncident(id)`

**Implementation**:
On mount, call `GET /api/incidents/`. Render a table or card list showing: title, category badge, severity colour-coded badge, status badge, location, occurred-at timestamp, and a link to the detail page. Include pagination controls. Show an empty state when the list is empty. Show a loading skeleton while fetching.

**Complexity**: M
**Dependencies**: Phase 1.4 (CORS must work), Phase 4.1 (neighborhoods API — users need to belong to a neighborhood to see incidents beyond their own; add a "no neighborhood" prompt if `neighborhood_memberships` is empty)
**Testing required**:
- Log in as resident with no incidents; confirm empty state
- Create an incident via API; confirm it appears in the list
- Log in as a different resident in a different neighborhood; confirm they cannot see the incident
- Test pagination controls
**Deployment impact**: Frontend only.

---

### 2.3 Incident Detail Page

**Problem**: `incident-detail.jsx` is a spinner. Backend `GET /api/incidents/{id}/` returns full incident data including media list.

**Files affected**:
- `frontend/src/pages/incident-detail.jsx` — full implementation

**Implementation**:
On mount, fetch the incident by `id` from URL params. Display all fields: title, description, category, severity, status (with a visual workflow indicator), location, reporter name, verified-by, assigned-to, timestamps. Display attached media as a thumbnail grid (image preview, video/audio icon). If the user is the reporter and the incident is PENDING, show an edit form. If the user is a coordinator, show a "Verify" button and a "Transition Status" dropdown.

**Complexity**: M
**Dependencies**: 2.2 (uses the same API functions)
**Testing required**:
- View incident as reporter; confirm edit fields visible
- View incident as non-reporter; confirm edit fields hidden
- View incident as coordinator; confirm Verify and Transition controls present
- Verify an incident; confirm status badge updates
**Deployment impact**: Frontend only.

---

### 2.4 Incident Creation Form

**Problem**: There is no "Report Incident" button or form anywhere in the frontend. Users have no way to create incidents via the UI.

**Files affected**:
- `frontend/src/pages/incidents.jsx` — add "Report Incident" button + modal or inline form
- `frontend/src/api.js` — add `createIncident(payload)` → `POST /api/incidents/`
- `frontend/src/pages/incident-detail.jsx` — navigate here on create success

**Implementation**:
Add a prominent "Report Incident" button on the incidents list page. On click, show a modal (or a `/incidents/new` route) with fields: title, description, category (select), severity (select), address (text), occurred_at (datetime), and neighborhood (select — populated from `GET /api/neighborhoods/` once that API exists; in Phase 2 use a hardcoded UUID or make it optional). GPS coordinates: add a "Use my location" button using the browser Geolocation API.

**Complexity**: M
**Dependencies**: 2.2, Phase 4.1 (neighborhood selector requires the neighborhoods API; use a placeholder until then)
**Testing required**:
- Submit form with valid data; confirm incident appears in list
- Submit with missing required fields; confirm field-level errors displayed
- Submit with invalid coordinates; confirm validation error
- Test "Use my location" button in browser
**Deployment impact**: Frontend only.

---

### 2.5 Verification Request Page

**Problem**: `verification.jsx` is a spinner. Backend `POST /api/verification-requests` is implemented.

**Files affected**:
- `frontend/src/pages/verification.jsx` — full implementation

**Implementation**:
Show the user's current `verification_status`. If already APPROVED, show a success message. If PENDING, show "Your request is under review." If RESIDENT or REJECTED, show a form with an optional "notes" textarea and a "Submit Verification Request" button that calls `POST /api/verification-requests`. On success, update the displayed status to PENDING.

**Complexity**: S
**Dependencies**: Phase 1.4 (CORS)
**Testing required**:
- Submit as unverified resident; confirm status changes to pending
- Submit again as pending resident; confirm error "A pending request already exists"
- Test as already-approved user; confirm no form shown
**Deployment impact**: Frontend only.

---

### 2.6 Coordinator Queue Page

**Problem**: `coordinator.jsx` is a spinner. Backend `GET /api/coordinator/verification-requests` and approve/reject endpoints are implemented.

**Files affected**:
- `frontend/src/pages/coordinator.jsx` — full implementation

**Implementation**:
On mount, fetch `GET /api/coordinator/verification-requests`. Render a list of pending verification requests showing: applicant name, email, phone, submission date, notes. For each: an "Approve" button and a "Reject" button with an optional reason text field. Add role guard: if `user.role.code !== 'coordinator' && user.role.code !== 'system_admin'`, show a 403 message instead of the list.

**Complexity**: S
**Dependencies**: 2.5 (verification submissions needed to test the queue)
**Testing required**:
- Log in as coordinator; confirm pending requests appear
- Approve a request; confirm it disappears from queue
- Reject a request with a reason; confirm the applicant's status updates
- Log in as resident; confirm access is denied
**Deployment impact**: Frontend only.

---

### 2.7 Profile Edit Form

**Problem**: `profile.jsx` is read-only. The `PATCH /api/users/me` endpoint and `updateProfile()` API function both exist.

**Files affected**:
- `frontend/src/pages/profile.jsx` — add edit mode toggle and form fields

**Implementation**:
Add an "Edit Profile" button. On click, replace the read-only display with input fields for: full_name, phone_number, address, latitude, longitude. Include profile photo upload. On "Save", call `PATCH /api/users/me`, then call `onUpdate(updatedUser)` to propagate the change to the header. Show field-level errors from the API response.

**Complexity**: S
**Dependencies**: None (API endpoint and `updateProfile` in `api.js` already exist)
**Testing required**:
- Update full_name; confirm change reflected in header without page reload
- Upload profile photo; confirm it appears
- Submit invalid phone number; confirm field error shown
**Deployment impact**: Frontend only.

---

### 2.8 Global Field-Level Error Handling

**Problem**: All form pages show `err.payload.detail` (top-level string) and ignore the field-level error dict DRF returns (e.g., `{"email": ["A user with this email already exists."]}`).

**Files affected**:
- `frontend/src/pages/login.jsx`
- `frontend/src/pages/register.jsx`
- Any new forms from 2.3–2.7

**Implementation**:
Create a utility function `extractErrors(payload)` that maps DRF's field error dict to the form's `errors` state. Call this on every catch block. Pass `errors[fieldName]` to each `<FormField error={...}>` prop.

```js
// frontend/src/api.js or a new frontend/src/utils/errors.js
export function extractErrors(payload) {
  if (!payload) return {};
  const { detail, ...fieldErrors } = payload;
  return fieldErrors;
}
```

**Complexity**: S
**Dependencies**: All form pages in this phase
**Testing required**:
- Register with a duplicate email; confirm "A user with this email already exists." appears below the email field, not as a generic banner
- Login with wrong password; confirm appropriate message
**Deployment impact**: Frontend only.

---

### Phase 2 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 2.1 OTP verification screen | S | 2 | Phase 1.1 |
| 2.2 Incidents list page | M | 2 | Phase 1.4 |
| 2.3 Incident detail page | M | 1 | 2.2 |
| 2.4 Incident creation form | M | 2 | 2.2 |
| 2.5 Verification request page | S | 1 | Phase 1.4 |
| 2.6 Coordinator queue page | S | 1 | 2.5 |
| 2.7 Profile edit form | S | 1 | None |
| 2.8 Field-level error handling | S | 3+ | All forms |

**Total estimated effort**: 8–12 days
**Gate to Phase 3**: Phases 2.2–2.6 should be complete before the infrastructure work in Phase 3, so the new infrastructure can be tested through the UI.

---

## Phase 3 — Infrastructure & Reliability
**Objective**: Make the backend production-reliable. This phase has no new user-facing features but fixes two categories of broken behaviour: files being lost on container restart (storage), and security claims that don't hold in production (rate limiting, media access control, OTP delivery, checksum, sync_version).

**Target completion**: 1 week

---

### 3.1 Wire Django Storage to MinIO

**Problem**: Media files write to the local container disk (`MEDIA_ROOT`). Files are lost on container restart or horizontal scaling. `django-storages[boto3]` is already installed.

**Files affected**:
- `backend/config/settings/base.py` — add `STORAGES` configuration block
- `backend/config/settings/local.py` — keep using filesystem storage for local dev
- `.env.example` — document the storage env vars

**Implementation**:
```python
# base.py — conditional storage backend
USE_S3_STORAGE = env_bool("USE_S3_STORAGE", False)

if USE_S3_STORAGE:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "endpoint_url": env("MINIO_ENDPOINT_URL"),
                "access_key": env("MINIO_ACCESS_KEY"),
                "secret_key": env("MINIO_SECRET_KEY"),
                "bucket_name": env("MINIO_BUCKET_NAME", "nhwz-media"),
                "file_overwrite": False,
                "default_acl": "private",  # never public
                "querystring_auth": True,  # signed URLs
                "querystring_expire": 3600,  # 1 hour
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
```

In `docker-compose.yml`, add `USE_S3_STORAGE=True` and the MinIO credentials to the `api` service env or `.env`.

**Complexity**: S
**Dependencies**: MinIO service in `docker-compose.yml` (already present)
**Testing required**:
- Upload an incident media file; confirm it appears in MinIO console at `localhost:9001`
- Fetch the media via the API; confirm the `file` URL is a signed MinIO URL, not a local path
- Stop and restart the `api` container; confirm uploaded files still accessible
**Deployment impact**: Requires `USE_S3_STORAGE=True` in the Docker environment. Existing files on local disk need migrating to MinIO before switching (or accept losing dev data). **Breaking change for any existing media files in production.**

---

### 3.2 Authenticated Media Serving

**Problem**: Nginx serves `/media/` files to anyone with the URL, bypassing JWT auth. Incident evidence must be private.

**Files affected**:
- `infra/nginx/default.conf` — remove or gate the `/media/` static block
- `backend/apps/incidents/views.py` or a new `core/views.py` view — add a media redirect view using X-Accel-Redirect (nginx) or signed URL redirect (MinIO/S3)

**Implementation** (with MinIO signed URLs from 3.1):
When `USE_S3_STORAGE=True`, the `file` field in `IncidentMediaSerializer` already returns a signed URL — authentication is handled by the S3 signature. The Nginx `/media/` block can simply be removed since files are no longer on local disk.

For local dev (`USE_S3_STORAGE=False`), add Django's `X-Accel-Redirect` pattern:
```python
# A lightweight view that checks auth then issues a redirect to an internal nginx path
# nginx: location /protected-media/ { internal; alias /media/; }
```

**Complexity**: S
**Dependencies**: 3.1 (storage backend)
**Testing required**:
- Request a media file URL without an `Authorization` header; expect 401 (or expired signed URL)
- Request with a valid token; expect the file
**Deployment impact**: Nginx config change + container restart. Breaks direct URL bookmarks to media files (intended).

---

### 3.3 Redis-Backed Rate Limiting

**Problem**: `SimpleRateThrottle` uses in-memory cache, not shared across Gunicorn workers. Rate limits are ineffective in multi-worker production.

**Files affected**:
- `backend/config/settings/base.py` — add `CACHES` configuration

**Implementation**:
```python
# base.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
```

This requires `django-redis` or Django 4.0+ built-in Redis cache backend (Django 5.2 ships it natively with no extra dependency).

**Complexity**: XS
**Dependencies**: Redis service (already in `docker-compose.yml`)
**Testing required**:
- With a 3-request-per-minute limit (set temporarily for testing), send 4 rapid requests; confirm the 4th returns HTTP 429
- Restart the Django process; confirm the counter persists (it's now in Redis)
- Run two parallel worker processes; confirm the shared counter applies across both
**Deployment impact**: Add `CACHES` to `.env`-driven settings. No migration needed.

---

### 3.4 Celery Worker Service

**Problem**: `docker-compose.yml` has no Celery worker. Even when tasks are added in later phases, nothing will consume the queue.

**Files affected**:
- `docker-compose.yml` — add `celery` service
- `backend/config/celery.py` — already correct, no change needed

**Implementation**:
```yaml
# docker-compose.yml — add service
celery:
  build:
    context: .
    dockerfile: infra/docker/backend.Dockerfile
  env_file:
    - .env
  command: celery -A config.celery worker --loglevel=info --concurrency=2
  depends_on:
    - redis
    - postgres
```

Also add a `celery-beat` service if periodic tasks are needed (Phase 6 analytics, Phase 3.6 OTP cleanup).

**Complexity**: XS
**Dependencies**: 3.3 (Redis cache should be working)
**Testing required**:
- `docker compose up`; confirm `celery` container starts and shows "celery@... ready"
- Run `celery inspect active` to confirm the worker is responsive
**Deployment impact**: New container. No breaking change to existing containers.

---

### 3.5 OTP Email Delivery

**Problem**: `OTPService.generate()` creates the challenge record but never sends the code to the user. SMS is the target but requires an external provider contract; email delivery can be shipped immediately.

**Files affected**:
- `backend/apps/accounts/services/otp_service.py` — call `send_otp_async` after creating the challenge
- `backend/apps/accounts/tasks.py` — **new file**, Celery task `send_otp_email`
- `backend/config/settings/base.py` — add `EMAIL_*` settings from env
- `backend/config/settings/local.py` — already has `console.EmailBackend`

**Implementation**:
```python
# apps/accounts/tasks.py
from celery import shared_task
from django.core.mail import send_mail

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_otp_email(self, recipient_email, code, purpose, expires_at):
    subject_map = {
        "registration": "Your Neighbourhood Watch verification code",
        "password_reset": "Reset your Neighbourhood Watch password",
        "phone_verification": "Your Neighbourhood Watch code",
    }
    try:
        send_mail(
            subject=subject_map.get(purpose, "Your one-time code"),
            message=f"Your one-time code is: {code}\n\nThis code expires at {expires_at} (UTC).",
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)
```

In `OTPService.generate()`, after creating the challenge, dispatch the task:
```python
from apps.accounts.tasks import send_otp_email
if channel == OTPChallenge.Channel.EMAIL:
    send_otp_email.delay(destination, code, purpose, str(expires_at))
```

For registration (currently SMS channel), either switch to EMAIL channel or add an SMS task stub.

**Complexity**: M
**Dependencies**: 3.4 (Celery worker must be running)
**Testing required**:
- Register a new account; confirm an email arrives at the registered address (use console backend in dev — check terminal output)
- Confirm the debug code in the API response matches the emailed code
- Simulate task failure (mock SMTP error); confirm task retries 3 times
- Confirm OTP still works after task retry delivers a new email
**Deployment impact**: Requires `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` in production `.env`.

---

### 3.6 Media Checksum Computation

**Problem**: `IncidentMedia.checksum` is always `""`. File integrity verification is non-functional.

**Files affected**:
- `backend/apps/incidents/views.py` — `upload_media` action, lines 270–282

**Implementation**:
```python
import hashlib

def _compute_sha256(file_obj):
    sha = hashlib.sha256()
    file_obj.seek(0)
    for chunk in file_obj.chunks():
        sha.update(chunk)
    file_obj.seek(0)
    return sha.hexdigest()

# In upload_media action, before IncidentMedia.objects.create():
checksum = _compute_sha256(file_obj)

media = IncidentMedia.objects.create(
    ...
    checksum=checksum,
)
```

**Complexity**: XS
**Dependencies**: None
**Testing required**:
- Upload a file; confirm `checksum` field in the response is a non-empty 64-character hex string
- Upload the same file twice; confirm both records have the same checksum
**Deployment impact**: Backend only. Existing records will have empty checksum (acceptable).

---

### 3.7 Increment `sync_version` on Incident Updates

**Problem**: `Incident.sync_version` is always `1`. Offline sync conflict detection (Phase 8) requires this to increment on every mutation.

**Files affected**:
- `backend/apps/incidents/services.py` — `transition()` and `assign()`
- `backend/apps/incidents/views.py` — `perform_update()`

**Implementation**:
Add `sync_version` to all `update_fields` lists and increment before saving:
```python
incident.sync_version = models.F("sync_version") + 1
incident.save(update_fields=[..., "sync_version"])
```

**Complexity**: XS
**Dependencies**: None
**Testing required**:
- Create an incident; confirm `sync_version = 1`
- Update title; confirm `sync_version = 2`
- Verify the incident; confirm `sync_version = 3`
**Deployment impact**: Backend only. Existing incidents retain version 1 (correct — they have had one "version").

---

### 3.8 Periodic OTP Challenge Cleanup

**Problem**: `OTPChallenge` records accumulate indefinitely. Expired and consumed challenges are never purged.

**Files affected**:
- `backend/apps/accounts/tasks.py` — add `cleanup_expired_otp_challenges`
- `docker-compose.yml` — add `celery-beat` service (or add a management command called from a cron)

**Implementation**:
```python
@shared_task
def cleanup_expired_otp_challenges():
    from django.utils import timezone
    from apps.accounts.models import OTPChallenge
    cutoff = timezone.now() - timedelta(days=7)
    deleted, _ = OTPChallenge.objects.filter(expires_at__lt=cutoff).delete()
    return f"Deleted {deleted} expired OTP challenges."
```

Schedule via Celery Beat:
```python
# config/celery.py
app.conf.beat_schedule = {
    "cleanup-otp-challenges": {
        "task": "apps.accounts.tasks.cleanup_expired_otp_challenges",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

**Complexity**: S
**Dependencies**: 3.4 (Celery worker), 3.5 (tasks.py file created)
**Testing required**:
- Create OTP challenges with `expires_at` in the past; run the task manually; confirm they are deleted
- Confirm active (unconsumed, unexpired) challenges are NOT deleted
**Deployment impact**: Requires Celery Beat container in production.

---

### Phase 3 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 3.1 MinIO storage wiring | S | 2 | None |
| 3.2 Authenticated media serving | S | 2 | 3.1 |
| 3.3 Redis-backed rate limiting | XS | 1 | None |
| 3.4 Celery worker in Docker | XS | 1 | 3.3 |
| 3.5 OTP email delivery | M | 2 | 3.4 |
| 3.6 Media checksum | XS | 1 | None |
| 3.7 sync_version increment | XS | 2 | None |
| 3.8 OTP cleanup task | S | 2 | 3.4, 3.5 |

**Total estimated effort**: 4–6 days
**Gate to Phase 4**: Storage and Celery must be working before the notification engine (Phase 5) is built on top of them.

---

## Phase 4 — Neighborhoods API
**Objective**: Expose the `Neighborhood` and `NeighborhoodMembership` models via the API. This is a load-bearing dependency: without it, clients cannot discover neighborhood UUIDs, users cannot join neighborhoods, the incident visibility rules never grant access to neighborhood incidents, and the coordinator queue is always empty.

**Target completion**: 3–5 days

---

### 4.1 Neighborhood CRUD Endpoints

**Files affected**:
- `backend/apps/neighborhoods/views.py` — **new file**
- `backend/apps/neighborhoods/serializers.py` — expand (currently exists but may be minimal)
- `backend/apps/neighborhoods/urls.py` — **new file**
- `backend/config/urls.py` — include neighborhoods URLs

**Endpoints to implement**:
```
GET    /api/neighborhoods/                  — list active neighborhoods (public)
POST   /api/neighborhoods/                  — create neighborhood (admin only)
GET    /api/neighborhoods/{id}/             — retrieve neighborhood detail
PATCH  /api/neighborhoods/{id}/             — update (admin only)
GET    /api/neighborhoods/{id}/members/     — list members (coordinator/admin)
POST   /api/neighborhoods/{id}/join/        — join a neighborhood (any authenticated user)
DELETE /api/neighborhoods/{id}/leave/       — leave a neighborhood
POST   /api/neighborhoods/{id}/members/{user_id}/role/  — change member role (coordinator/admin)
```

**Implementation notes**:
- `GET /api/neighborhoods/` must be accessible without authentication (residents need to see options before joining)
- The `boundary_geojson` field should be optional in all responses to keep list payloads small
- `join` creates a `NeighborhoodMembership` with `role=RESIDENT` and `is_primary=True` if none exists

**Complexity**: M
**Dependencies**: None (models already exist)
**Testing required**:
- 10–15 tests: list neighborhoods, create (admin), join, leave, list members, change role, duplicate join attempt
- Confirm RBAC: non-admins cannot create neighborhoods, non-coordinators cannot change member roles
**Deployment impact**: New URL routes registered. No migrations needed.

---

### 4.2 Frontend Neighborhood Selector

**Files affected**:
- `frontend/src/api.js` — add `fetchNeighborhoods()`, `joinNeighborhood(id)`
- `frontend/src/pages/profile.jsx` — add "My Neighborhoods" section with join/leave
- `frontend/src/pages/incidents.jsx` — populate neighborhood dropdown in creation form (from 2.4)

**Implementation**:
In the profile page, show the user's current neighborhood memberships with a "Join a Neighborhood" button that opens a modal listing available neighborhoods from `GET /api/neighborhoods/`.

**Complexity**: S
**Dependencies**: 4.1, Phase 2.7 (profile page edit form)
**Testing required**:
- Join a neighborhood; confirm incidents from that neighborhood appear in the list
- Leave a neighborhood; confirm incidents disappear
**Deployment impact**: Frontend only.

---

### Phase 4 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 4.1 Neighborhood CRUD API | M | 4 | None |
| 4.2 Frontend neighborhood selector | S | 3 | 4.1, Phase 2 |

**Total estimated effort**: 3–5 days

---

## Phase 5 — Notification Engine
**Objective**: Deliver real-time alerts to users when incidents are created and verified in their neighborhood. This is the first user-visible async feature — it requires the Celery infrastructure from Phase 3 and the neighborhood membership data from Phase 4.

**Target completion**: 1–2 weeks

---

### 5.1 Notification Preference Model & API

**Files affected**:
- `backend/apps/notifications/models.py` — add `NotificationPreference` model
- New migration
- `backend/apps/notifications/serializers.py` — add preference serializer
- `backend/apps/notifications/views.py` — **new file**, preference endpoints
- `backend/apps/notifications/urls.py` — **new file**
- `backend/config/urls.py` — include notifications URLs

**Endpoints**:
```
GET    /api/me/notifications/                    — inbox (paginated)
PATCH  /api/me/notifications/{id}/read/          — mark as read
DELETE /api/me/notifications/{id}/              — soft-delete
GET    /api/me/notification-preferences/         — get channel opt-ins
PUT    /api/me/notification-preferences/         — update opt-ins
```

**Complexity**: M
**Dependencies**: Phase 4.1 (neighborhood context needed for filtering)
**Testing required**: 8–10 tests covering inbox retrieval, mark-read, delete, preference get/set.
**Deployment impact**: New migration, new URL routes.

---

### 5.2 Incident Notification Fanout (Celery Task)

**Problem**: When an incident is created or verified, users in the affected neighborhood are never notified.

**Files affected**:
- `backend/apps/notifications/tasks.py` — **new file**
- `backend/apps/incidents/views.py` — `perform_create` and `verify` action: dispatch task
- `backend/apps/notifications/services.py` — **new file**, `NotificationDispatchService`

**Implementation**:
```python
# notifications/tasks.py
@shared_task
def notify_neighborhood_incident(incident_id, event_type):
    incident = Incident.objects.select_related("neighborhood").get(id=incident_id)
    if not incident.neighborhood_id:
        return
    members = NeighborhoodMembership.objects.filter(
        neighborhood_id=incident.neighborhood_id,
        deleted_at__isnull=True,
    ).exclude(user_id=incident.reporter_id).select_related("user")

    notifications = [
        Notification(
            recipient=m.user,
            incident=incident,
            channel=Notification.Channel.DASHBOARD,
            status=Notification.Status.QUEUED,
            priority=Notification.Priority.HIGH if incident.severity == "red" else Notification.Priority.NORMAL,
            title=f"New incident: {incident.title}",
            body=f"A {incident.get_severity_display()} incident was reported in {incident.neighborhood.name}.",
        )
        for m in members
    ]
    Notification.objects.bulk_create(notifications)
```

Call from `perform_create`:
```python
from apps.notifications.tasks import notify_neighborhood_incident
notify_neighborhood_incident.delay(str(incident.id), "created")
```

**Complexity**: M
**Dependencies**: 3.4 (Celery), 5.1 (Notification model), Phase 4.1 (NeighborhoodMembership)
**Testing required**:
- Create an incident; confirm `Notification` records created for all neighborhood members
- Verify an incident; confirm another notification wave dispatched
- Confirm reporter does not receive a self-notification
- Test `CELERY_TASK_ALWAYS_EAGER=True` for synchronous test execution
**Deployment impact**: Requires Celery worker running.

---

### 5.3 Email Notification Channel

**Files affected**:
- `backend/apps/notifications/tasks.py` — add `send_email_notification` task
- `backend/apps/notifications/services.py` — add `EmailProvider` class

**Complexity**: M
**Dependencies**: 3.5 (OTP email delivery — establishes the email plumbing), 5.2
**Testing required**: Mock SMTP; confirm email sent with correct subject and body. Test retry on SMTP failure.
**Deployment impact**: Uses existing email settings from Phase 3.5.

---

### 5.4 SMS Notification Channel (Twilio)

**Files affected**:
- `backend/apps/notifications/services.py` — add `SMSProvider` class using Twilio REST client
- `requirements.txt` — add `twilio`
- `.env.example` — document `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`

**Complexity**: M
**Dependencies**: 5.3 (same Celery task pattern)
**Testing required**: Use Twilio test credentials; confirm `MessageInstance` created. Mock in unit tests.
**Deployment impact**: Requires Twilio account and credentials in production `.env`. Not blocked: gracefully skip SMS if credentials not set.

---

### Phase 5 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 5.1 Notification preference API | M | 5 | Phase 4.1 |
| 5.2 Incident fanout Celery task | M | 3 | Phase 3.4, 5.1 |
| 5.3 Email notification channel | M | 2 | Phase 3.5, 5.2 |
| 5.4 SMS channel (Twilio) | M | 2 | 5.3 |

**Total estimated effort**: 1–2 weeks

---

## Phase 6 — SOS Module & Emergency Contacts
**Objective**: Implement the SOS alert flow end-to-end: a user in danger can trigger an SOS that notifies their emergency contacts and nearby coordinators/police. Models already exist; this phase adds the API surface and dispatch logic.

**Target completion**: 1 week

---

### 6.1 Emergency Contact Management API

**Files affected**:
- `backend/apps/accounts/views.py` — add `EmergencyContactViewSet`
- `backend/apps/accounts/serializers.py` — add `EmergencyContactSerializer`
- `backend/apps/accounts/urls.py` — add `/api/me/emergency-contacts/` routes

**Endpoints**:
```
GET    /api/me/emergency-contacts/           — list
POST   /api/me/emergency-contacts/           — create
PATCH  /api/me/emergency-contacts/{id}/      — update
DELETE /api/me/emergency-contacts/{id}/      — soft-delete
```

**Complexity**: S
**Dependencies**: None (model already exists)
**Testing required**: 5–8 tests: CRUD, priority uniqueness constraint, max contacts limit.
**Deployment impact**: New URL routes, no migration.

---

### 6.2 SOS Alert API

**Files affected**:
- `backend/apps/sos/views.py` — **new file**
- `backend/apps/sos/serializers.py` — expand
- `backend/apps/sos/urls.py` — **new file**
- `backend/config/urls.py` — include sos URLs
- `backend/apps/sos/tasks.py` — **new file**, emergency contact dispatch task

**Endpoints**:
```
POST   /api/sos/                             — create SOS alert (sets status=ACTIVE)
POST   /api/sos/{id}/ping/                   — add location ping
POST   /api/sos/{id}/resolve/                — mark resolved/cancelled
GET    /api/sos/active/                      — list active alerts (coordinator/police)
```

**Dispatch task**: On SOS creation, send SMS (via 5.4) to all `EmergencyContact` records with `can_receive_sos=True`. Also create `Notification` records for coordinators in the user's primary neighborhood.

**Complexity**: L
**Dependencies**: 5.4 (SMS dispatch), 6.1 (emergency contacts)
**Testing required**: 10–15 tests: create SOS, add pings, resolve, dispatch to contacts, cancel.
**Deployment impact**: New migration (no schema changes needed — model exists), new URL routes, Celery task.

---

### 6.3 Frontend SOS Button

**Files affected**:
- `frontend/src/components/layout.jsx` — add persistent SOS button in header
- `frontend/src/api.js` — add `createSosAlert()`, `resolveSosAlert(id)`
- `frontend/src/pages/sos.jsx` — **new file**, active SOS tracking screen

**Implementation**: A prominent red "SOS" button in the header, always visible to authenticated users. On click, confirm dialog → `POST /api/sos/` → show a live screen with "Alert sent to N contacts" and a Cancel button. Use browser Geolocation API for coordinates.

**Complexity**: M
**Dependencies**: 6.2
**Testing required**: Click SOS; confirm API call made; confirm emergency contact receives notification (in dev: check console email backend).
**Deployment impact**: Frontend rebuild.

---

### Phase 6 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 6.1 Emergency contact API | S | 3 | None |
| 6.2 SOS alert API + dispatch | L | 5 | Phase 5.4, 6.1 |
| 6.3 Frontend SOS button | M | 3 | 6.2 |

**Total estimated effort**: 5–8 days

---

## Phase 7 — Geospatial Queries & Analytics
**Objective**: Activate PostGIS (production-only) to enable proximity-based incident discovery, neighborhood boundary containment, and risk heatmaps. Add analytics snapshot generation for coordinator dashboards.

**Target completion**: 1–2 weeks

---

### 7.1 Geospatial Service Layer

**Files affected**:
- `backend/apps/incidents/services.py` — add `IncidentGeospatialService`
- New PostgreSQL-only test profile (`backend/config/settings/postgres_test.py`)

**Implementation**:
```python
class IncidentGeospatialService:
    @staticmethod
    def nearby_incidents(lat, lon, radius_m, statuses=None):
        from django.contrib.gis.geos import Point
        from django.contrib.gis.db.models.functions import Distance
        point = Point(float(lon), float(lat), srid=4326)
        qs = Incident.objects.annotate(distance=Distance("location", point))
        if radius_m:
            qs = qs.filter(distance__lte=radius_m)
        if statuses:
            qs = qs.filter(status__in=statuses)
        return qs.order_by("distance")
```

Note: This requires adding a `geography` column to `Incident`. Use a conditional migration that only runs on PostGIS databases (pattern already established in `core.0002_postgis_foundation`).

**Complexity**: L
**Dependencies**: Production PostgreSQL + PostGIS (dev continues using SQLite with decimal lat/lon)
**Testing required**: Separate test class marked `@tag("postgis")` that runs against a real PostgreSQL + PostGIS instance. Test radius, boundary, edge cases (null location, zero radius).
**Deployment impact**: Requires PostGIS migration on production database. SQLite dev environment unaffected.

---

### 7.2 Geospatial API Endpoints

**Files affected**:
- `backend/apps/incidents/views.py` — add `nearby` action to `IncidentViewSet`
- `backend/apps/neighborhoods/views.py` — add `risk_summary` endpoint

**Endpoints**:
```
GET /api/incidents/nearby/?latitude=X&longitude=Y&radius_m=5000
GET /api/neighborhoods/{id}/risk-summary/
GET /api/incidents/heatmap/?bounds=minLat,minLon,maxLat,maxLon
```

**Complexity**: M
**Dependencies**: 7.1
**Testing required**: Integration tests using PostGIS test profile. Test that SQLite-based tests still pass (geospatial endpoints return 503 or 404 on SQLite).
**Deployment impact**: New endpoints, no breaking change.

---

### 7.3 Analytics Snapshot Generation

**Files affected**:
- `backend/apps/analytics/tasks.py` — **new file**, `generate_neighborhood_snapshot`
- `backend/apps/analytics/views.py` — **new file**, read-only snapshot endpoint
- `backend/apps/analytics/urls.py` — **new file**
- `backend/config/urls.py` — include analytics URLs
- Celery Beat schedule update

**Endpoints**:
```
GET /api/neighborhoods/{id}/analytics/?period=7d
```

**Task**: Daily snapshot counting incidents by category, severity, and status per neighborhood. Written to `AnalyticsSnapshot.metrics` as JSON.

**Complexity**: M
**Dependencies**: 3.4 (Celery Beat), Phase 4 (neighborhoods)
**Testing required**: Run task on test data; confirm snapshot created with correct metric counts.
**Deployment impact**: New Celery Beat schedule entry, new URL routes, new migration if needed.

---

### Phase 7 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 7.1 Geospatial service (PostGIS) | L | 2 | PostGIS in prod |
| 7.2 Nearby + heatmap endpoints | M | 2 | 7.1 |
| 7.3 Analytics snapshots | M | 4 | Phase 3.4, Phase 4 |

**Total estimated effort**: 8–12 days

---

## Phase 8 — Real-Time, Offline Sync & Production Hardening
**Objective**: Add WebSocket-based live updates, the offline sync API for the mobile client, and complete all production-readiness work: Kubernetes manifests, CI/CD, security audit, and load testing.

**Target completion**: 3–4 weeks

---

### 8.1 WebSocket Consumer (Incident Updates)

**Files affected**:
- `backend/apps/core/consumers.py` — **new file**, `IncidentUpdateConsumer`
- `backend/config/asgi.py` — add WebSocket routing
- `frontend/src/api.js` — add WebSocket client

**Implementation**: Django Channels `WebsocketConsumer` that subscribes to a `neighborhood_{id}` group. When an incident is created or status-changed, broadcast to the group. Frontend connects on the incidents list page and refreshes the list on receiving a message.

**Complexity**: L
**Dependencies**: Phase 5.2 (incident events already dispatched via Celery — fan into WebSocket group from the same task), Phase 4 (neighborhood groups)
**Testing required**: `channels.testing.WebsocketCommunicator` tests. Test authentication (unauthenticated WS connections must be rejected).
**Deployment impact**: Requires `daphne` (ASGI) replacing Gunicorn (WSGI) in Docker, or running both. `channels[daphne]` already in `requirements.txt`.

---

### 8.2 Offline Sync API

**Files affected**:
- `backend/apps/sync/views.py` — **new file**
- `backend/apps/sync/services.py` — **new file**, delta sync and conflict resolution
- `backend/apps/sync/urls.py` — **new file**
- `backend/config/urls.py` — include sync URLs

**Endpoints**:
```
POST /api/sync/              — submit pending mutations (create/update/delete)
GET  /api/sync/delta/?since=<ISO-timestamp>  — server-side changes since timestamp
```

**Implementation**: The `POST /api/sync/` endpoint processes `SyncQueue` items idempotently using `idempotency_key`. The `GET /api/sync/delta/` endpoint returns incidents, notifications, and profile changes modified after `since`, using `last_modified_at` indexes (already on the models).

**Complexity**: XL
**Dependencies**: 3.7 (`sync_version` must be incrementing), all feature phases
**Testing required**: 15–20 tests covering idempotent create, conflict detection, delta query, authentication.
**Deployment impact**: New URL routes, no schema change.

---

### 8.3 Kubernetes Manifests

**Files affected**:
- `k8s/` — **new directory** with manifests for: `api-deployment.yaml`, `celery-deployment.yaml`, `postgres-statefulset.yaml`, `redis-deployment.yaml`, `minio-statefulset.yaml`, `nginx-ingress.yaml`, `secrets.yaml`, `configmap.yaml`, `hpa.yaml` (HorizontalPodAutoscaler for the API)

**Complexity**: L
**Dependencies**: All phases (manifests should reflect the final service topology)
**Testing required**: Deploy to a local `minikube` or `k3s` cluster; run smoke tests against each endpoint.
**Deployment impact**: This IS the deployment change. No breaking change to Docker Compose path.

---

### 8.4 CI/CD Pipeline

**Files affected**:
- `.github/workflows/ci.yml` — **new file**
- `.github/workflows/cd.yml` — **new file** (optional, deploy on merge to main)

**CI steps**:
1. Backend: `python manage.py test apps --settings=config.settings.test`
2. Backend: `python manage.py check --settings=config.settings.production`
3. Frontend: `npm run build` (lint + build)
4. Docker: `docker build` to confirm the image builds
5. (Optional) PostGIS tests on a `postgres:postgis` service container

**Complexity**: M
**Dependencies**: None (can be added at any phase)
**Testing required**: The CI pipeline is the test.
**Deployment impact**: None (CI runs on PR, CD deploys after merge).

---

### 8.5 Security Hardening

**Files affected**: Multiple

**Checklist**:
- [ ] Add `python-magic` for server-side MIME type detection on media uploads (`backend/apps/incidents/serializers.py`)
- [ ] Fix `X-Forwarded-For` IP extraction in `audit/services.py` to use the last trusted hop (or configure `NUM_PROXIES` in DRF)
- [ ] Add `SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"` to production settings
- [ ] Audit all endpoints that expose UUIDs — confirm they can't be enumerated to access other users' data
- [ ] Add `django-axes` for account lockout after repeated failed logins (complements rate limiting)
- [ ] Rotate the development secret key (`"local-development-secret-key"`) so it cannot be accidentally used in production (make `DJANGO_SECRET_KEY` required in `base.py`, not just `production.py`)

**Complexity**: M
**Dependencies**: Phase 3 complete (infrastructure stable before security hardening)
**Testing required**: OWASP ZAP scan against staging environment; manual penetration test of auth endpoints.
**Deployment impact**: Secret key rotation requires reissuing all existing JWTs.

---

### 8.6 Flutter Mobile App

**Files affected**:
- `mobile/` — **new directory**, Flutter project

**Screens**:
- Auth: Login, Registration, OTP verification
- Incidents: List, Detail, Create (with camera integration)
- SOS: Emergency button with GPS, contact notification status
- Notifications: Inbox with action buttons
- Profile: Edit, neighborhood membership, emergency contacts

**Complexity**: XL
**Dependencies**: All backend phases complete; 8.1 (WebSocket for real-time), 8.2 (offline sync for offline-first)
**Testing required**: Widget tests, integration tests on iOS simulator and Android emulator. Use `flutter_test` and `mockito`.
**Deployment impact**: Separate APK/IPA release pipeline. No backend change.

---

### Phase 8 Summary

| Item | Complexity | Files | Depends On |
|---|---|---|---|
| 8.1 WebSocket consumers | L | 3 | Phase 5.2, 4 |
| 8.2 Offline sync API | XL | 4 | All phases, 3.7 |
| 8.3 Kubernetes manifests | L | 10+ | All phases |
| 8.4 CI/CD pipeline | M | 2 | None |
| 8.5 Security hardening | M | 5+ | Phase 3 |
| 8.6 Flutter mobile app | XL | 50+ | All phases |

**Total estimated effort**: 6–10 weeks (Flutter dominates)

---

## Dependency Graph

```
Phase 1 (Critical Fixes)
    │
    ├──→ Phase 2 (Frontend Core)        [can start in parallel with Phase 3]
    │        │
    │        └──→ Phase 4.2 (Neighborhood selector UI)
    │
    ├──→ Phase 3 (Infrastructure)
    │        │
    │        ├──→ Phase 4 (Neighborhoods API)
    │        │        │
    │        │        ├──→ Phase 5 (Notifications)
    │        │        │        │
    │        │        │        └──→ Phase 6 (SOS)
    │        │        │                  │
    │        │        │                  └──→ Phase 7 (Geospatial + Analytics)
    │        │        │                            │
    │        │        └──────────────────────────→ Phase 8 (Real-time, Sync, K8s, Flutter)
    │        │
    │        └──→ Phase 8.4 (CI/CD)    [can start any time]
    │
    └──→ Phase 8.5 (Security hardening) [after Phase 3]
```

---

## Sprint Planning Reference

| Sprint | Phases | Focus | Deliverable |
|---|---|---|---|
| Sprint 1 (Week 1) | 1 + 2.1–2.4 | Crash fixes, core UI pages | App is usable end-to-end |
| Sprint 2 (Week 2) | 2.5–2.8 + 3.1–3.4 | Verification UI, infrastructure | Storage working, rate limiting real |
| Sprint 3 (Week 3) | 3.5–3.8 + 4.1 | OTP delivery, cleanup, neighborhoods API | OTP emails land, neighborhoods discoverable |
| Sprint 4 (Week 4) | 4.2 + 5.1–5.2 | Neighborhood UI, notification fanout | Users notified on incident creation |
| Sprint 5 (Week 5–6) | 5.3–5.4 + 6.1–6.2 | Email/SMS channels, SOS API | SMS alerts, SOS dispatch working |
| Sprint 6 (Week 7) | 6.3 + 7.1–7.3 | SOS frontend, geospatial, analytics | Heatmaps, SOS button, dashboards |
| Sprint 7 (Week 8–9) | 8.1–8.5 | Real-time, K8s, CI/CD, security | Production-ready deployment |
| Sprint 8 (Week 10–14) | 8.6 | Flutter mobile app | Mobile client shipped |

---

## Test Count Targets by Phase

| Phase | New Tests | Running Total |
|---|---|---|
| Baseline (Phase 1–2, current) | 36 | 36 |
| Phase 2 (frontend — unit/component) | 20 | 56 |
| Phase 3 (infrastructure) | 12 | 68 |
| Phase 4 (neighborhoods) | 15 | 83 |
| Phase 5 (notifications) | 25 | 108 |
| Phase 6 (SOS) | 18 | 126 |
| Phase 7 (geospatial + analytics) | 20 | 146 |
| Phase 8 (real-time + sync) | 30 | 176 |
| Phase 8 (Flutter) | 40 | 216 |

Target at GA: **200+ tests, 80%+ backend coverage**

---

*End of roadmap — 2026-06-26*
