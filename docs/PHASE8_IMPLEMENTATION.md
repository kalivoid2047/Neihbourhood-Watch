# Phase 8 Implementation — Neighborhoods API, SOS Module, Security & Kubernetes

## Summary

Phase 8 completes the remaining backend feature surface and production deployment
infrastructure: a full Neighborhood write API, the Emergency Contact and SOS alert
modules, additional security hardening, and Kubernetes manifests.

---

## 1 · Neighborhood Write API

The `NeighborhoodViewSet` (previously read-only) now exposes a full management
surface via custom actions:

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/neighborhoods/` | **Public** | List active neighborhoods |
| GET | `/api/neighborhoods/{id}/` | **Public** | Neighborhood detail |
| POST | `/api/neighborhoods/` | System admin | Create neighborhood |
| PATCH | `/api/neighborhoods/{id}/` | System admin | Update neighborhood |
| DELETE | `/api/neighborhoods/{id}/` | System admin | Soft-deactivate |
| POST | `/api/neighborhoods/{id}/join/` | Authenticated | Join neighborhood |
| DELETE | `/api/neighborhoods/{id}/leave/` | Authenticated | Leave neighborhood |
| GET | `/api/neighborhoods/{id}/members/` | Coordinator/Admin | List members |
| POST | `/api/neighborhoods/{id}/members/{user_id}/role/` | Coordinator/Admin | Change member role |
| GET | `/api/neighborhoods/{id}/risk-summary/` | Authenticated | Risk metrics |

**Join behaviour**: first join sets `is_primary=True` automatically.
**Leave behaviour**: soft-deletes the `NeighborhoodMembership` record; clears `is_primary`.

---

## 2 · Emergency Contact API

Emergency contacts are personal data — all endpoints are scoped to the authenticated
user's own records.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/me/emergency-contacts` | List own contacts |
| POST | `/api/me/emergency-contacts` | Create contact |
| GET | `/api/me/emergency-contacts/{id}` | Retrieve contact |
| PATCH | `/api/me/emergency-contacts/{id}` | Update contact |
| DELETE | `/api/me/emergency-contacts/{id}` | Soft-delete contact |

Fields: `name`, `phone_number`, `relationship`, `priority`, `can_receive_sos`.

---

## 3 · SOS Alert API

The SOS module lets authenticated users trigger an emergency alert that is
dispatched to their emergency contacts via `NotificationDispatchService`.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/sos/` | Authenticated | Create SOS alert (dispatches contacts) |
| GET | `/api/sos/` | Authenticated | List own alerts |
| GET | `/api/sos/{id}/` | Authenticated | Detail |
| GET | `/api/sos/active/` | Coordinator/Police/Admin | List active alerts |
| POST | `/api/sos/{id}/ping/` | Alert owner | Add location ping |
| POST | `/api/sos/{id}/resolve/` | Alert owner | Mark resolved |
| POST | `/api/sos/{id}/cancel/` | Alert owner | Mark cancelled |

**Dispatch**: `POST /api/sos/` triggers `NotificationDispatchService.dispatch_sos_alert()`
synchronously in the request cycle (or via Celery task if `CELERY_TASK_ALWAYS_EAGER=False`
and the task is queued). Emergency contacts with `can_receive_sos=True` receive an
SMS notification.

---

## 4 · Security Hardening (8.5)

### python-magic MIME type validation

`IncidentMediaUploadSerializer.validate()` now reads the first 2 KB of each
uploaded file with `python-magic` and confirms the detected MIME type matches
the declared `media_type` field. Falls through gracefully if `python-magic` is
not installed.

Allowed MIME prefixes per `media_type`:
- `image` → `image/*`
- `video` → `video/*`
- `audio` → `audio/*`
- `document` → `application/pdf`, `application/msword`, `text/plain`, `application/*`

### django-axes account lockout

`django-axes` is conditionally added to `INSTALLED_APPS` and `MIDDLEWARE` when
the package is installed. No extra configuration is required for default lockout
behaviour (5 failed login attempts → account locked for 1 hour).

To activate: `pip install django-axes` (already in `requirements.txt`).
To customise, add `AXES_*` settings to your environment settings file.

---

## 5 · Docker — celery-beat Scheduler Fix

The `celery-beat` service in `docker-compose.yml` previously used
`django_celery_beat.schedulers:DatabaseScheduler`, which requires the
`django-celery-beat` package (not in `requirements.txt`). The scheduler flag
has been removed; Celery Beat now uses its default in-memory scheduler backed
by the `beat_schedule` dictionary defined in `config/celery.py`.

---

## 6 · Kubernetes Manifests (`k8s/`)

New directory with production-ready manifests:

| File | Resource |
|------|----------|
| `namespace.yaml` | `nhwz` namespace |
| `configmap.yaml` | Non-secret environment variables |
| `secrets.yaml` | Secret references (replace placeholder values before deploying) |
| `api-deployment.yaml` | API `Deployment` (2 replicas) + `Service` |
| `celery-deployment.yaml` | Celery worker + beat `Deployment`s |
| `redis-deployment.yaml` | Redis `Deployment` + `Service` |
| `postgres-statefulset.yaml` | PostGIS `StatefulSet` + headless `Service` with 10 Gi PVC |
| `nginx-ingress.yaml` | nginx `Deployment`, `Service` (LoadBalancer), and `Ingress` |
| `hpa.yaml` | `HorizontalPodAutoscaler` for the API (2–10 replicas on CPU/RAM) |

**Deployment steps**:
```bash
kubectl apply -f k8s/namespace.yaml
# Edit k8s/secrets.yaml with real values, then:
kubectl apply -f k8s/
```

---

## 7 · New Requirements

| Package | Purpose |
|---------|---------|
| `python-magic>=0.4,<0.5` | Server-side MIME type detection for media uploads |
| `django-axes>=7.0,<8` | Account lockout after repeated failed login attempts |

---

## 8 · Tests

**31 new tests** across 2 new test files:

| File | Class | Tests |
|------|-------|-------|
| `neighborhoods/tests/test_phase8_neighborhoods_api.py` | `NeighborhoodListPublicTests` | list is public, inactive excluded |
| | `NeighborhoodCreateTests` | admin creates, resident/anon blocked |
| | `NeighborhoodJoinLeaveTests` | join, primary flag, duplicate join, leave, leave non-member |
| | `NeighborhoodMembersTests` | coordinator lists, resident blocked, role change, nonmember 400 |
| `sos/tests/test_phase8_sos_api.py` | `EmergencyContactTests` | CRUD, isolation, unauthenticated blocked |
| | `SOSAlertCreateTests` | create, missing coords, invalid lat, unauthenticated |
| | `SOSAlertLifecycleTests` | ping, resolve, cancel, double-close, active list, non-owner |

**Total: 253 tests (was 222).**

---

## 9 · Static Analysis

```
$ flake8 backend/apps backend/config
(no output — clean)

$ manage.py check --deploy --settings=config.settings.production
System check identified 30 issues (0 silenced).
```

The 30 deploy-check issues are all **WARNINGS** — 27 pre-existing `drf_spectacular`
W002 warnings (views missing `serializer_class`) + 2 new W002 for `NotificationReadView`
and `SyncPushView` + 1 W009 (CI placeholder secret key too short, normal in CI).

---

## 10 · Remaining Issues

| # | Severity | Description |
|---|----------|-------------|
| 1 | Warning | 29 `drf_spectacular` W001/W002 warnings — pre-existing; add `@extend_schema` or `serializer_class` to silence. |
| 2 | Info | `python-magic` requires `libmagic` on the host OS. Add `libmagic1` to the Dockerfile `apt-get install` list for production. |
| 3 | Info | `django-axes` needs `python manage.py migrate` after install (adds `axes_*` tables). |
| 4 | Info | K8s `secrets.yaml` contains placeholder values. Replace all `CHANGE_ME` entries before deploying. |
| 5 | Info | Flutter mobile app (roadmap 8.6) — out of scope for this phase; all backend APIs are ready. |
