# Phase 3 Implementation: Incident Reporting APIs

## Completion Summary

Phase 3 fully implements incident reporting with comprehensive RBAC, incident lifecycle management, and media evidence workflows.

### New Components Added

**Permissions** (`apps/incidents/permissions.py`):
- `CanViewIncident`: View permission enforcing incident visibility by role and neighborhood.
- `CanVerifyIncident`: Coordinators and admins can verify pending incidents.
- `CanAssignIncident`: Coordinators and admins can assign incidents.
- `CanUploadIncidentMedia`: Media upload permission for incident reporters and authorized users.

**Services** (`apps/incidents/services.py`):
- `IncidentStatusTransitionService`: Manages state machine transitions (PENDING → VERIFIED → INVESTIGATING → RESOLVED → CLOSED) with audit logging.

**Serializers** (`apps/incidents/serializers.py`):
- `IncidentListSerializer`: Lightweight incident list view.
- `IncidentSerializer`: Full incident detail with media list and user names.
- `IncidentCreateSerializer`: Incident creation (auto-assigns reporter).
- `IncidentUpdateSerializer`: Update allowed fields before verification.
- `IncidentStatusTransitionSerializer`: Status change requests.
- `IncidentAssignmentSerializer`: Assign incident to user.
- `IncidentMediaUploadSerializer`: Media upload with file size validation (max 100MB).

**Views** (`apps/incidents/views.py`):
- `IncidentViewSet`: Full CRUD with role-based queryset filtering.
  - `GET /api/incidents/` — List incidents visible to user.
  - `POST /api/incidents/` — Create incident (defaults to PENDING).
  - `GET /api/incidents/{id}/` — Retrieve incident detail with media.
  - `PATCH /api/incidents/{id}/` — Update incident fields (reporter only).
  - `POST /api/incidents/{id}/verify/` — Verify incident (coordinators/admins).
  - `POST /api/incidents/{id}/transition_status/` — Status transition (coordinators/admins).
  - `POST /api/incidents/{id}/assign/` — Assign incident (coordinators/admins).
  - `GET /api/incidents/{id}/media/` — List incident media.
  - `POST /api/incidents/{id}/upload_media/` — Upload media (multipart).
- `IncidentMediaDetailView`: Retrieve or soft-delete media.

**URLs** (`apps/incidents/urls.py`):
- Registered incidents viewset and media detail routes.

### RBAC Matrix

| Role | Create | Update Own | View Own | View Neighborhood | Verify | Assign | Upload Media |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Resident | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Block Captain | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Coordinator | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Police Officer | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| System Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### Status Transition State Machine

```
PENDING → VERIFIED → INVESTIGATING → RESOLVED → CLOSED
       ↓           ↓                ↓
       └──────────→ CLOSED ←────────┘
```

- **PENDING**: New incident, awaiting coordinator review.
- **VERIFIED**: Coordinator confirmed incident, can proceed to investigation.
- **INVESTIGATING**: Active investigation underway.
- **RESOLVED**: Issue resolved, awaiting closure.
- **CLOSED**: Final state, no further transitions.

### Incident Visibility Rules

- **Reporters** see their own incidents.
- **Neighborhood members** (residents, block captains, coordinators) see all neighborhood incidents.
- **Assigned users** see incidents assigned to them (bypasses neighborhood check).
- **System admins** see all incidents.

### Media Upload

- Max file size: 100MB.
- Supported types: image, video, audio.
- Stored in MinIO (S3-compatible).
- Media metadata (mime type, size, checksum) recorded.
- Audit logged on upload and soft-delete.

### Audit Logging

All incident actions are audit-logged:
- `incident_created` — On creation.
- `incident_updated` — On field update.
- `incident_status_changed_to_{status}` — On status transition.
- `incident_assigned` — On assignment.
- `incident_media_uploaded` — On media upload.
- `incident_media_deleted` — On media soft-delete.

### Tests

18 new comprehensive tests in `apps/incidents/tests/test_phase3_incidents_api.py`:

**CRUD Tests**:
- Residents can create incidents (default PENDING status).
- Residents can update own incidents.
- Other residents cannot update incidents.
- Residents cannot view incidents outside their neighborhood.
- System admins can view all incidents.
- Incident list respects role and neighborhood.

**Status Transition Tests**:
- Coordinators can verify pending incidents.
- Residents cannot verify incidents.
- Invalid transitions are rejected.
- Valid transition sequences work (PENDING → VERIFIED → INVESTIGATING → RESOLVED).

**Media Tests**:
- Reporters can upload media.
- Unauthenticated users cannot upload.
- Media list retrieval works.
- File size validation.

**Assignment Tests**:
- Coordinators can assign incidents.
- Residents cannot assign.
- Assigned users can view incident outside neighborhood.

### API Usage Examples

**Create Incident**:
```bash
curl -X POST http://localhost:8080/api/incidents/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "neighborhood": "uuid",
    "title": "Suspicious Activity",
    "description": "...",
    "category": "suspicious_activity",
    "severity": "blue",
    "latitude": "17.8252",
    "longitude": "31.0335",
    "address": "...",
    "occurred_at": "2024-01-15T10:00:00Z"
  }'
```

**Verify Incident** (coordinator):
```bash
curl -X POST http://localhost:8080/api/incidents/{id}/verify/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"new_status": "verified"}'
```

**Upload Media**:
```bash
curl -X POST http://localhost:8080/api/incidents/{id}/upload_media/ \
  -H "Authorization: Bearer {token}" \
  -F "media_type=image" \
  -F "file=@photo.jpg" \
  -F "metadata={}"
```

**Assign Incident** (coordinator):
```bash
curl -X POST http://localhost:8080/api/incidents/{id}/assign/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"assigned_to_id": "user-uuid"}'
```

**List Incidents** (visible to authenticated user):
```bash
curl http://localhost:8080/api/incidents/ \
  -H "Authorization: Bearer {token}"
```

### Integration Status

✓ Phase 1 tests: 2/2 passing
✓ Phase 2 tests: 16/16 passing
✓ Phase 3 tests: 18/18 passing
**Total: 36/36 tests passing**

✓ Django system checks: OK
✓ Docker build: OK
✓ API health: OK

### Next Steps

Phase 4 (Geospatial Queries) will:
- Implement PostGIS-based radius searches and neighborhood geofencing.
- Add nearby incidents, risk summaries, and hotspot detection.
- Maintain SQLite-compatible tests for non-spatial logic.

Phase 5 (Notification Engine) will:
- Implement notification dispatch with Firebase, SMS, and dashboard providers.
- Add Celery tasks for async fanout and retries.
- Implement alert distribution for verified incidents and SOS.
