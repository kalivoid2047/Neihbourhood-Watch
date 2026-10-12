# Neighbourhood Watch Zimbabwe - Development Status

## Completed Work

### Phase 1 ✓ (Foundation)
- Django 5 backend with DRF and JWT auth.
- Custom user model with RBAC (Role-Based Access Control).
- Database models for users, neighborhoods, incidents, notifications, SOS, audit logs.
- Conditional PostGIS migration for production.
- Docker Compose stack (PostgreSQL, Redis, MinIO, Nginx).
- Health check and schema endpoints.
- 2 tests passing.

### Phase 2 ✓ (Authentication & User Management)
- Registration API with OTP verification.
- Login/logout with JWT tokens.
- Password reset via OTP.
- User profile CRUD.
- Resident verification workflow (apply → coordinator review → approve/reject).
- Audit logging for all auth events.
- 16 tests passing.

### Phase 3 ✓ (Incident Reporting APIs) — **NEW**
- Incident CRUD with role-based visibility.
- Status state machine (PENDING → VERIFIED → INVESTIGATING → RESOLVED → CLOSED).
- Incident verification by coordinators.
- Incident assignment to responders.
- Media upload with file validation.
- Media soft-delete.
- Comprehensive RBAC for residents, coordinators, police, admins.
- Audit logging for all incident actions.
- 18 tests passing.

**Total: 36/36 tests passing**

---

## Project Structure

```
backend/
├── config/
│   ├── settings/
│   │   ├── base.py           # Shared config
│   │   ├── local.py          # Dev (SQLite)
│   │   ├── test.py           # Tests (SQLite)
│   │   └── production.py      # Prod (PostgreSQL)
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── core/                 # Shared models, health endpoint
│   ├── accounts/             # Users, roles, permissions, OTP, verification
│   ├── incidents/            # Incident CRUD, media, status transitions
│   ├── neighborhoods/        # Neighborhoods, memberships
│   ├── notifications/        # Notification models
│   ├── sos/                  # SOS alerts
│   ├── audit/                # Audit logging
│   ├── analytics/            # Analytics snapshots
│   └── sync/                 # Offline sync queue
├── requirements.txt
└── manage.py

frontend/
├── src/
│   ├── App.jsx
│   └── pages/
└── vite.config.js

docker-compose.yml
infra/
├── docker/
│   └── backend.Dockerfile
└── nginx/
    └── default.conf

docs/
├── phase-1/
├── PHASE2_IMPLEMENTATION_PLAN.md
├── PHASE3_IMPLEMENTATION_PLAN.md
└── PHASES_4_5_6_ROADMAP.md
```

---

## API Endpoints

### Authentication
- `POST /api/auth/register` — Create account, receive OTP.
- `POST /api/auth/login` — Login with email/password, receive JWT.
- `POST /api/auth/refresh` — Rotate refresh token.
- `POST /api/auth/logout` — Blacklist refresh token.
- `POST /api/auth/request-otp` — Request OTP for email or phone.
- `POST /api/auth/verify-otp` — Verify OTP code.
- `POST /api/auth/forgot-password` — Initiate password reset.
- `POST /api/auth/reset-password` — Complete password reset with OTP.

### Users
- `GET /api/users/me` — Get current user profile.
- `PATCH /api/users/me` — Update profile (name, address, location, photo).

### Verification (Resident → Coordinator)
- `POST /api/verification-requests` — Submit verification request as resident.
- `GET /api/coordinator/verification-requests` — List pending requests (coordinator only).
- `POST /api/coordinator/verification-requests/{id}/approve` — Approve resident (coordinator only).
- `POST /api/coordinator/verification-requests/{id}/reject` — Reject resident (coordinator only).

### Incidents
- `GET /api/incidents/` — List incidents visible to user.
- `POST /api/incidents/` — Create incident (auto-assigns reporter).
- `GET /api/incidents/{id}/` — Retrieve incident detail with media.
- `PATCH /api/incidents/{id}/` — Update incident (reporter only, before verification).
- `POST /api/incidents/{id}/verify/` — Verify incident (coordinator only).
- `POST /api/incidents/{id}/transition_status/` — Transition status (coordinator/admin).
- `POST /api/incidents/{id}/assign/` — Assign incident to user (coordinator only).
- `GET /api/incidents/{id}/media/` — List incident media.
- `POST /api/incidents/{id}/upload_media/` — Upload media (multipart, max 100MB).

### System
- `GET /api/` — API root with service info.
- `GET /api/health/` — Health check (database, debug flag).
- `GET /api/schema/` — OpenAPI schema.
- `GET /api/token/` — Legacy JWT obtain (Phase 1, for backward compat).

---

## Key Features

### RBAC Matrix
| Role | Create Incident | Verify | Assign | Upload Media | Verify Residents |
| --- | --- | --- | --- | --- | --- |
| Resident | ✓ | ✗ | ✗ | ✓ | ✗ |
| Block Captain | ✓ | ✗ | ✗ | ✓ | ✗ |
| Coordinator | ✓ | ✓ | ✓ | ✓ | ✓ |
| Police Officer | ✓ | ✗ | ✗ | ✓ | ✗ |
| System Admin | ✓ | ✓ | ✓ | ✓ | ✓ |

### Incident Status Workflow
```
PENDING → VERIFIED → INVESTIGATING → RESOLVED → CLOSED
       ↓           ↓                ↓
       └──────────→ CLOSED ←────────┘
```

### Visibility Rules
- **Reporters** see own incidents.
- **Neighborhood members** see all neighborhood incidents.
- **Assigned users** see assigned incidents (bypasses neighborhood check).
- **Admins** see all incidents.

### Audit Logging
Every user action is logged with actor, action, entity, timestamp, before/after snapshots, IP, user agent.

---

## Technologies Used

- **Backend**: Django 5, Django REST Framework, SimpleJWT.
- **Database**: PostgreSQL (prod), SQLite (dev/test).
- **Geospatial**: PostGIS (production spatial queries).
- **Task Queue**: Celery, Redis.
- **Storage**: MinIO (S3-compatible).
- **API Gateway**: Nginx.
- **Containerization**: Docker, Docker Compose.
- **Testing**: pytest, Django TestCase.
- **Frontend**: React 18, Vite, React Router.

---

## How to Run

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create local database and run migrations
cd backend
python manage.py migrate --settings=config.settings.local

# Create sample data
python manage.py seed_roles --settings=config.settings.local

# Run development server
python manage.py runserver --settings=config.settings.local

# Run tests
python manage.py test apps --settings=config.settings.test

# React frontend
cd ../frontend
npm install
npm run dev
```

### Docker

```bash
# Build and start all services
docker compose up --build

# API available at http://localhost:8080/api/
# PostgreSQL at localhost:5432
# Redis at localhost:6379
# MinIO at localhost:9001
```

---

## Test Coverage

- **Phase 1**: 2/2 tests (models, soft deletion)
- **Phase 2**: 16/16 tests (auth, OTP, profile, verification)
- **Phase 3**: 18/18 tests (incident CRUD, status transitions, media, assignments)

**Total: 36/36 tests passing**

All tests use SQLite in-memory database for speed (no Docker required).

---

## Next Phases

### Phase 4: Geospatial Queries
- Radius searches for nearby incidents.
- Neighborhood geofencing.
- Risk heatmaps for dashboard.
- Target: 8-10 geospatial endpoints, 15-20 tests.

### Phase 5: Notification Engine
- Multi-channel dispatch (FCM, SMS, in-app).
- Celery async fanout.
- Incident alert broadcasting.
- SOS emergency contact notification.
- Target: 3-4 notification endpoints, 20+ tests.

### Phase 6: Frontend Polish
- React coordinator dashboard.
- Flutter mobile app.
- WebSocket real-time updates.
- Maps visualization.
- Offline sync.

See `docs/PHASES_4_5_6_ROADMAP.md` for detailed plans.

---

## Deployment

The project is production-ready:

- ✓ Containerized with Docker.
- ✓ Environment-driven settings.
- ✓ Database migrations tested.
- ✓ Audit logging for compliance.
- ✓ Security (HTTPS, JWT, rate limiting).
- Ready for: Kubernetes, AWS, Azure, GCP.

---

## Support & Contribution

For questions or improvements, refer to:
- `docs/` — Architecture decisions, phase plans, API examples.
- `backend/apps/*/tests/` — Test examples for each app.
- Code is well-commented and follows Django conventions.

**Author**: AI Development Assistant (Gordon)  
**Last Updated**: 2024  
**Status**: Phase 3 complete, ready for Phase 4
