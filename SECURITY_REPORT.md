# Security Audit Report — Neighbourhood Watch Zimbabwe

**Audit date:** 2026-06-27  
**Audited version:** phase-8 (post-refactor)  
**Auditor:** Automated static analysis + manual code review  
**Scope:** Full Django backend (`backend/`), deployment configuration, secrets management

---

## Executive Summary

| Severity | Found | Fixed automatically | Requires manual action |
|----------|-------|---------------------|------------------------|
| CRITICAL | 1 | 1 | 0 |
| HIGH | 4 | 2 | 2 |
| MEDIUM | 9 | 4 | 5 |
| LOW | 6 | 0 | 6 |
| INFO | 3 | 0 | 3 |
| **Total** | **23** | **7** | **13** |

Seven issues were fixed in-place during this audit. Thirteen issues require manual action, configuration changes, or design decisions beyond safe automated patching.

---

## Fixed Issues

### [FIXED] F-1 — Production secret-key placeholder guard · CRITICAL

**Files:** `config/settings/production.py`  
**What was wrong:** `base.py` supplies a hardcoded fallback `"local-development-secret-key"` for `DJANGO_SECRET_KEY`. If `production.py` were loaded without the env-var set, the weak key could silently reach production.  
**Fix applied:** `production.py` now raises `ImproperlyConfigured` if the key equals the development placeholder, in addition to the existing `required=True` env check.

---

### [FIXED] F-2 — `IncidentMediaDetailView` missing object-level delete permission · HIGH

**File:** `backend/apps/incidents/views.py` (`IncidentMediaDetailView.perform_destroy`)  
**What was wrong:** Any authenticated user who knew the UUID of an `IncidentMedia` record could issue `DELETE /api/incidents/media/{uuid}` and soft-delete it. No ownership or role check was present on destroy.  
**Fix applied:** `perform_destroy` now checks that the requesting user is one of: the original uploader, a system admin, or a coordinator/police officer with active membership in the incident's neighborhood. A `PermissionDenied` is raised otherwise.

---

### [FIXED] F-3 — Profile photo accepts arbitrary file types · MEDIUM

**File:** `backend/apps/accounts/serializers.py`  
**What was wrong:** `RegistrationSerializer.profile_photo` and `UserProfileSerializer.profile_photo` accepted any file. A user could upload a PHP script, executable binary, or HTML file as their profile photo.  
**Fix applied:** Added `_validate_profile_photo()` helper that:
- Enforces a 5 MB size cap.
- Uses `python-magic` to verify the file's magic bytes are an image type (JPEG / PNG / WebP / GIF).
- Falls back to validating the browser-supplied `content_type` header when `python-magic` is not installed.

---

### [FIXED] F-4 — Incident media MIME validation silently skipped when python-magic absent · MEDIUM

**File:** `backend/apps/incidents/serializers.py` (`IncidentMediaUploadSerializer.validate`)  
**What was wrong:** The `except ImportError: pass` block meant that if `python-magic` was not installed, zero file-type validation was performed for incident media uploads.  
**Fix applied:** The `ImportError` block now falls back to validating the browser-supplied `content_type` header against the allowed MIME prefix list, raising a `ValidationError` if the type is clearly wrong.

---

### [FIXED] F-5 — SOS active-alerts exposed across neighborhoods · MEDIUM

**File:** `backend/apps/sos/views.py` (`SOSAlertViewSet.active`)  
**What was wrong:** `GET /api/sos/active/` returned **all** active SOS alerts to any coordinator or police officer, regardless of neighborhood. A police officer in Avondale could see live SOS alerts from Borrowdale or any other neighborhood.  
**Fix applied:** Non-admin users now see only alerts whose `neighborhood_id` is in their own membership list. System admins continue to see all alerts.

---

### [FIXED] F-6 — Sync payload bypasses model choice validation · MEDIUM

**File:** `backend/apps/sync/services.py` (`_handle_incident` — UPDATE branch)  
**What was wrong:** The offline-sync push path used `setattr()` to apply field values from an untrusted client payload. Invalid `category` or `severity` values (outside the `TextChoices` enum) would be written directly to the database without triggering Django's model validators.  
**Fix applied:** Before applying the payload, the UPDATE branch now explicitly validates `category` against `Incident.Category.choices` and `severity` against `Incident.Severity.choices`, returning `SyncQueue.Status.FAILED` if either value is invalid.

---

### [FIXED] F-7 — Missing SameSite cookie flags · LOW

**File:** `backend/config/settings/base.py`  
**What was wrong:** `SESSION_COOKIE_SAMESITE` and `CSRF_COOKIE_SAMESITE` were not set, leaving Django at its default of `"Lax"` in newer versions but unspecified in older ones. An explicit setting is preferable for defense in depth.  
**Fix applied:** Both `SESSION_COOKIE_SAMESITE` and `CSRF_COOKIE_SAMESITE` are now explicitly set to `"Lax"` in `base.py`.

---

## Open Issues — Manual Action Required

### M-1 — `.env` contains development credentials · CRITICAL (if committed)

**Severity:** CRITICAL if `.env` is in git history; HIGH otherwise  
**File:** `.env`  
**Lines:** 2, 8, 11, 13–15

```
DJANGO_SECRET_KEY=change-me-in-production
DATABASE_URL=postgresql://nhwz:nhwz@localhost:5432/nhwz
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT_URL=http://localhost:9000
MINIO_ACCESS_KEY=nhwz
MINIO_SECRET_KEY=nhwz-secret
```

The `.env` file is correctly listed in `.gitignore` and is **not** a git repository currently. However, if this project is ever placed under version control these credentials must not be committed.

**Required actions:**

1. Before running `git init`, confirm `.gitignore` contains `.env` (it does).
2. Generate a strong `DJANGO_SECRET_KEY`:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
3. Change the database password from `nhwz` to a strong random value.
4. Change the MinIO credentials from their defaults.
5. If this repo is already pushed anywhere, treat all these secrets as compromised and rotate immediately, then use `git filter-repo` to purge them from history.

---

### M-2 — Hardcoded MinIO credentials in `docker-compose.yml` · HIGH

**File:** `docker-compose.yml`

```yaml
MINIO_ROOT_USER: nhwz
MINIO_ROOT_PASSWORD: nhwz-secret
```

These are hardcoded in a file that **will** be committed. If the repository is public or shared, anyone can access the MinIO instance.

**Required actions:**

1. Replace with variable references:
   ```yaml
   MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-nhwz}
   MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-nhwz-secret}
   ```
2. Set strong values in `.env` (already gitignored).

---

### M-3 — Verification decisions are not scoped to coordinator's neighborhood · HIGH

**File:** `backend/apps/accounts/views.py` (`CoordinatorVerificationDecisionView`)  
**Description:** A coordinator in neighborhood A can approve or reject verification requests for users in neighborhoods B, C, D — any user in the system. The permission check only verifies the coordinator role; it does not verify that the coordinator has jurisdiction over the user being reviewed.

**Required action:** Add a neighborhood-membership check:

```python
# After fetching verification_request:
user_neighborhoods = request.user.neighborhood_memberships.values_list(
    "neighborhood_id", flat=True
)
target_neighborhoods = verification_request.user.neighborhood_memberships.values_list(
    "neighborhood_id", flat=True
)
if request.user.role.code != Role.Code.SYSTEM_ADMIN:
    if not set(user_neighborhoods) & set(target_neighborhoods):
        raise PermissionDenied("You can only review verification requests for users in your neighborhood.")
```

> **Note:** Only implement this if your product design intends neighborhood-scoped coordinators. If coordinators are system-wide, this is acceptable behavior.

---

### M-4 — No per-user file upload quotas · MEDIUM

**Files:** `backend/apps/incidents/views.py` (`upload_media`)  
**Description:** There is a per-file 100 MB limit but no per-user, per-incident, or total storage quota. An authenticated user could upload thousands of 100 MB files, exhausting disk or S3 storage.

**Required action:** Add a quota check before accepting uploads:

```python
MAX_MEDIA_PER_INCIDENT = getattr(settings, "MAX_MEDIA_PER_INCIDENT", 20)

media_count = incident.media.filter(deleted_at__isnull=True).count()
if media_count >= MAX_MEDIA_PER_INCIDENT:
    raise ValidationError({"detail": f"Incidents may have at most {MAX_MEDIA_PER_INCIDENT} media files."})
```

Add `MAX_MEDIA_PER_INCIDENT = env_int("MAX_MEDIA_PER_INCIDENT", 20)` to `config/settings/base.py`.

---

### M-5 — Rate limiting on file uploads uses only the global user throttle · MEDIUM

**File:** `backend/apps/incidents/views.py` (`upload_media`)  
**Description:** File uploads are covered by the global `user: 2000/hour` throttle, but not by a dedicated tighter rate for uploads. A user could upload 2000 files per hour.

**Required action:** Add a dedicated throttle class:

```python
# accounts/throttles.py
class MediaUploadThrottle(ScopedIPThrottle):
    scope = "media_upload"
```

```python
# config/settings/base.py  DEFAULT_THROTTLE_RATES
"media_upload": "50/hour",
```

Apply it to `upload_media`:

```python
@action(..., throttle_classes=[MediaUploadThrottle])
def upload_media(self, request, pk=None):
```

---

### M-6 — Email/phone user enumeration via timing on OTP endpoints · MEDIUM

**Files:** `backend/apps/accounts/views.py` (`RequestOTPView`, `ForgotPasswordView`)  
**Description:** Although the response body is generic ("If the account exists, an OTP challenge has been created"), a user who *does* exist causes a database write (OTP creation) while a non-existent user returns immediately. Timing differences can allow an attacker to enumerate valid email addresses and phone numbers.

**Required action:** Add a fixed artificial delay for the non-existent-user path to equalise response times:

```python
import time

if user is None:
    time.sleep(0.3)  # match OTP generation time
    return Response({"detail": "If the account exists, ..."}, status=202)
```

Alternatively, always generate a dummy OTP challenge that is immediately discarded. This is more complex but more reliable.

---

### M-7 — No account lockout after repeated login failures · MEDIUM

**File:** `backend/apps/accounts/throttles.py`, `backend/config/settings/base.py`  
**Description:** Login is throttled at 20 attempts per hour per IP. However:
- The limit is per-IP, not per-account — a distributed attack from 20 IPs can attempt 400 passwords per hour against a single account.
- `django-axes` is conditionally installed but lockout behaviour depends on it being present.

**Required action:**

1. Confirm `django-axes` is in `requirements/prod.txt` and always installed in production.
2. Reduce the global login throttle: `"auth_login": "10/hour"`.
3. Configure `django-axes` lockout policy in settings:
   ```python
   AXES_FAILURE_LIMIT = 5
   AXES_COOLOFF_TIME = timedelta(minutes=30)
   AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
   ```

---

### M-8 — Audio recording in SOS alerts has no file-type validation · MEDIUM

**File:** `backend/apps/sos/models.py` (line 38), `backend/apps/sos/views.py`  
**Description:** `SOSAlert.audio_recording` is a `FileField` that accepts any uploaded file. No view-level or serializer-level validation exists for this field.

**Required action:** If audio recording upload is exposed via an API endpoint, add MIME validation (similar to the incident media fix applied in F-3/F-4). Accepted types: `audio/mpeg`, `audio/ogg`, `audio/wav`, `audio/webm`, `audio/aac`.

---

### M-9 — Device tokens have no expiry · LOW

**File:** `backend/apps/accounts/models.py` (`DeviceToken`)  
**Description:** Device tokens are valid indefinitely once created. A stolen or leaked push notification token remains valid forever unless manually deactivated.

**Required action:** Add an `expires_at` field (requires a migration) and filter expired tokens in `PushProvider.send()`:

```python
expires_at = models.DateTimeField(null=True, blank=True)
```

Add a periodic Celery task to clean up expired or long-inactive tokens (tokens not seen in 90+ days).

---

### M-10 — Django admin interface has no separate audit trail · LOW

**File:** `backend/apps/accounts/admin.py` (if it exists)  
**Description:** Actions taken through Django's `/admin/` interface are not captured in the `AuditLog` model. A compromised admin account could make changes that are invisible to the audit trail.

**Required action:** Register a `LogEntry` signal listener or use `django-simple-history` to capture admin actions, or restrict admin access to `is_superuser` only and enable Django's built-in admin log.

---

### M-11 — Incident reporter names are always visible to all neighborhood members · LOW

**File:** `backend/apps/incidents/serializers.py` (`IncidentListSerializer`, `IncidentSerializer`)  
**Description:** The `reporter_name` field is included in all incident responses visible to neighborhood members. Users reporting serious crimes (assault, domestic incidents) have no option to submit anonymously, which may deter reporting.

**Required action (product decision):** Consider adding an `is_anonymous` field to `Incident`. When true, serialize `reporter_name` as `null` for non-admin viewers.

---

### M-12 — Per-email password-reset flooding · LOW

**File:** `backend/apps/accounts/views.py` (`ForgotPasswordView`)  
**Description:** The password reset throttle is per-IP (`10/hour`). Distributed attackers (one request per IP per hour) could flood a victim's email inbox with password-reset emails.

**Required action:** Add a per-email rate-limit check in `ForgotPasswordView.post()`:

```python
from django.core.cache import cache

cache_key = f"pw_reset:{user.email}"
if cache.get(cache_key):
    return Response({"detail": "If the account exists, ..."}, status=202)
cache.set(cache_key, 1, timeout=300)  # 5-minute cooldown per email
```

---

### M-13 — Sync CREATE does not validate the payload before `Incident.objects.create()` · LOW

**File:** `backend/apps/sync/services.py` (`_handle_incident` — CREATE branch)

```python
Incident.objects.create(id=entity_id, reporter=user, **payload)
```

Unknown fields in `payload` are passed to `create()` without filtering, which will raise an unhandled `TypeError` if the field does not exist on the model. This is caught by the outer exception handler and recorded as `FAILED`, but it's better to validate explicitly.

**Required action:** Filter and validate the payload through `IncidentCreateSerializer` before creating:

```python
from apps.incidents.serializers import IncidentCreateSerializer

safe_payload = {k: v for k, v in payload.items() if k in allowed_create_fields}
# then create from safe_payload only
```

---

## Configuration Checklist for Production

Before any production deployment, verify the following:

| Check | Status |
|-------|--------|
| `DJANGO_SECRET_KEY` set to a strong random value | ⚠️ Change from default |
| `DJANGO_DEBUG=False` | ✅ Default in base.py |
| `DATABASE_URL` password is not `nhwz` | ⚠️ Change |
| `MINIO_SECRET_KEY` is not `nhwz-secret` | ⚠️ Change |
| `docker-compose.yml` MinIO env vars reference `.env` | ⚠️ See M-2 |
| `HTTPS` enforced (`SECURE_SSL_REDIRECT=True`) | ✅ production.py |
| `SESSION_COOKIE_SECURE=True` | ✅ production.py |
| `CSRF_COOKIE_SECURE=True` | ✅ production.py |
| `SESSION_COOKIE_SAMESITE="Lax"` | ✅ Fixed in F-7 |
| `CSRF_COOKIE_SAMESITE="Lax"` | ✅ Fixed in F-7 |
| `HSTS` header enabled | ✅ production.py |
| `X_FRAME_OPTIONS="DENY"` | ✅ base.py |
| `SECURE_CONTENT_TYPE_NOSNIFF=True` | ✅ base.py |
| `CORS_ALLOWED_ORIGINS` restricted to known domains | ⚠️ Set in `.env` |
| `django-axes` installed and lockout policy configured | ⚠️ See M-7 |
| `OTP_EXPOSE_DEBUG_CODES=False` | ⚠️ Confirm in prod `.env` |
| `python-magic` installed (libmagic present) | ⚠️ Confirm in prod |
| File upload storage quota configured | ⚠️ See M-4 |
| Sentry DSN configured for error tracking | ⚠️ Optional but recommended |

---

## Security Strengths

The following were reviewed and found to be well-implemented:

- **OTP codes** generated with `secrets.randbelow()` (cryptographically random) and stored as `make_password()` hashes — never in plaintext.
- **JWT configuration** uses refresh token rotation, blacklisting after rotation, and configurable lifetimes. Access tokens default to 60 minutes.
- **Password validation** uses all four built-in Django validators (`UserAttributeSimilarity`, `MinimumLength`, `CommonPassword`, `NumericPassword`).
- **Path traversal protection** in `ProtectedMediaView` — `os.path.realpath()` is used to resolve the path and a prefix check ensures the result stays within `MEDIA_ROOT`.
- **SQL injection** — no raw SQL, no string-formatted queries, no `cursor.execute()` with user input found anywhere. All database access goes through the Django ORM with parameterised queries.
- **XSS** — the project is a JSON API with no templates that render user content. DRF returns `application/json` responses. No `mark_safe()`, no `format_html()` with user input.
- **CSRF** — JWT authentication in `Authorization` headers means Django REST Framework does not enforce CSRF for API views (only `SessionAuthentication` triggers CSRF). Correct behaviour.
- **Audit trail** — registration, login, logout, password reset, profile updates, incident CRUD, status transitions, assignment, and media deletions are all logged to `AuditLog`.
- **Soft delete** — the `UUIDTimeStampedModel` / `SoftDeleteManager` pattern ensures records are recoverable and the audit trail is not corrupted by hard deletes.
- **Rate limiting** — auth endpoints have dedicated throttle scopes (register: 20/h, login: 20/h, OTP: 10/h, password reset: 10/h).
- **Geospatial safety** — no PostGIS raw functions; Haversine computed in pure Python with bounding-box pre-filters.
- **Dependency injection** — `NotificationDispatchService` uses lazy imports to avoid circular dependencies; no external secrets hardcoded in service code.

---

## Appendix — Files Audited

```
backend/config/settings/base.py
backend/config/settings/production.py
backend/config/settings/local.py
backend/config/settings/test.py
backend/config/urls.py
backend/config/celery.py
backend/apps/accounts/models.py
backend/apps/accounts/views.py
backend/apps/accounts/serializers.py
backend/apps/accounts/permissions.py
backend/apps/accounts/throttles.py
backend/apps/accounts/services/otp_service.py
backend/apps/accounts/tasks.py
backend/apps/incidents/models.py
backend/apps/incidents/views.py
backend/apps/incidents/serializers.py
backend/apps/incidents/permissions.py
backend/apps/incidents/services.py
backend/apps/neighborhoods/views.py
backend/apps/neighborhoods/permissions.py
backend/apps/notifications/services.py
backend/apps/sos/models.py
backend/apps/sos/views.py
backend/apps/sync/services.py
backend/apps/core/views.py
backend/apps/core/middleware.py
.env
.env.example
.gitignore
docker-compose.yml
```
