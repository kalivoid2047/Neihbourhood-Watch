# Neighbourhood Watch Zimbabwe

> A modern, community-driven security and emergency response platform for Zimbabwean neighborhoods.

[![Phase](https://img.shields.io/badge/Phase-3-blue)](https://github.com/your-repo)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/your-repo)
[![Tests](https://img.shields.io/badge/Tests-36%2F36%20Passing-brightgreen)](https://github.com/your-repo)

**Table of Contents**
- [Features](#features)
- [System Architecture](#system-architecture)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [Deployment Guide](#deployment-guide)
- [Development Guide](#development-guide)
- [FAQ](#faq)
- [Support](#support)

---

## Features

### Phase 1 ✅ - Foundation
- **Custom User Model**: Email-based authentication with role-based access control
- **Database Schema**: UUID primary keys, soft deletion, audit logging
- **PostGIS Support**: Production-ready geospatial database layer
- **Docker Stack**: PostgreSQL, Redis, MinIO, Nginx orchestration

### Phase 2 ✅ - Authentication & User Management
- **Registration**: Email/phone with OTP verification
- **Authentication**: JWT-based stateless sessions
- **Profile Management**: Edit profile, location tracking
- **Verification Workflow**: Resident verification by coordinators
- **Audit Logging**: All user actions logged for compliance

### Phase 3 ✅ - Incident Reporting (NEW)
- **Incident CRUD**: Create, read, update, delete with role-based visibility
- **Status Workflow**: PENDING → VERIFIED → INVESTIGATING → RESOLVED → CLOSED
- **Incident Verification**: Coordinators verify and validate incidents
- **Incident Assignment**: Assign to emergency responders
- **Media Evidence**: Upload images, videos, audio with validation
- **RBAC Enforcement**: 5 roles with granular permissions
- **Real-Time Audit Logging**: Track all changes with before/after snapshots

---

## System Architecture

### Frontend (React + Vite)
```
frontend/
├── src/
│   ├── pages/              # Route components
│   ├── components/         # Reusable UI components
│   │   ├── ui.jsx         # Tailwind component library
│   │   └── layout.jsx     # Header, footer, page layouts
│   ├── styles/            # Global CSS and Tailwind
│   ├── api.js             # API client with auth
│   └── App.jsx            # Main router
├── tailwind.config.js     # Design system config
└── vite.config.js         # Build configuration
```

**Tech Stack**:
- React 18 with Hooks
- React Router v6
- Tailwind CSS 3
- Lucide React (icons)
- Vite (build tool)
- Axios (HTTP client)

### Backend (Django + DRF)
```
backend/
├── config/
│   ├── settings/          # Environment-driven config
│   │   ├── base.py       # Shared settings
│   │   ├── local.py      # Development (SQLite)
│   │   ├── test.py       # Testing (SQLite)
│   │   └── production.py # Production (PostgreSQL)
│   └── urls.py           # URL routing
├── apps/
│   ├── core/             # Shared models, health endpoint
│   ├── accounts/         # Users, auth, OTP, verification
│   ├── incidents/        # Incident CRUD, media, status transitions
│   ├── neighborhoods/    # Neighborhoods, memberships
│   ├── notifications/    # Notification models
│   ├── sos/              # SOS alerts
│   ├── audit/            # Audit logging
│   ├── analytics/        # Analytics snapshots
│   └── sync/             # Offline sync queue
└── requirements.txt      # Python dependencies
```

**Tech Stack**:
- Django 5.2
- Django REST Framework
- SimpleJWT (JWT auth)
- PostgreSQL + PostGIS
- Celery + Redis
- MinIO (S3-compatible storage)
- Gunicorn (WSGI server)

### Infrastructure
```
docker-compose.yml
├── api          # Django backend (Gunicorn)
├── postgres     # PostgreSQL 16 + PostGIS
├── redis        # Redis for tasks & sessions
├── minio        # Object storage
└── nginx        # Reverse proxy & static files

infra/
├── docker/
│   └── backend.Dockerfile
└── nginx/
    └── default.conf
```

---

## Getting Started

### Prerequisites

- **Node.js**: v18+ (for frontend)
- **Python**: 3.10+ (for backend)
- **Docker**: v20+ (for containerized development)
- **Git**: For version control

### Local Development (No Docker)

#### 1. Backend Setup

```bash
# Clone repository
git clone <repo-url>
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create database
python manage.py migrate --settings=config.settings.local

# Seed roles and permissions
python manage.py seed_roles --settings=config.settings.local

# Create superuser (optional)
python manage.py createsuperuser --settings=config.settings.local

# Run development server
python manage.py runserver --settings=config.settings.local
# API available at http://localhost:8000/api/
```

#### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Frontend available at http://localhost:5173/

# Build for production
npm run build

# Preview production build
npm run preview
```

#### 3. Test Backend

```bash
cd backend

# Run all tests
python manage.py test apps --settings=config.settings.test

# Run specific app tests
python manage.py test apps.accounts --settings=config.settings.test

# Run with verbose output
python manage.py test apps --settings=config.settings.test -v 2
```

### Docker Development (Recommended)

```bash
# Start all services
docker compose up --build

# Logs
docker compose logs -f api

# Stop services
docker compose down

# Reset database
docker compose down -v
docker compose up --build
```

**Services**:
- Frontend: http://localhost:5173 (dev mode) or http://localhost:8080 (prod via nginx)
- Backend API: http://localhost:8000
- PostgreSQL: localhost:5432 (user: `nhwz`, password: `nhwz`)
- Redis: localhost:6379
- MinIO: http://localhost:9001 (user: `nhwz`, password: `nhwz-secret`)
- Nginx: http://localhost:8080

---

## API Documentation

### Base URL
```
Development: http://localhost:8000/api
Production: https://api.example.com/api
```

### Authentication
All endpoints except `/auth/*` require a JWT token in the `Authorization` header:
```
Authorization: Bearer <access_token>
```

Tokens expire after 1 hour. Use the refresh token to get a new access token:
```bash
POST /api/auth/refresh
{
  "refresh": "<refresh_token>"
}
```

### Core Endpoints

#### Authentication

```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "John Doe",
  "phone_number": "+263771234567",
  "national_id": "12345678A",
  "address": "123 Main St",
  "latitude": "17.8252",
  "longitude": "31.0335"
}

Response: 201 Created
{
  "user": {...},
  "tokens": {
    "access": "eyJ...",
    "refresh": "eyJ..."
  },
  "otp": {
    "challenge_id": "uuid",
    "expires_at": "2024-01-15T10:00:00Z",
    "debug_code": "123456"  # Only in development
  }
}
```

```http
POST /api/auth/login
{
  "email": "user@example.com",
  "password": "secure_password"
}

Response: 200 OK
{
  "user": {...},
  "tokens": {
    "access": "eyJ...",
    "refresh": "eyJ..."
  }
}
```

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
{
  "refresh": "<refresh_token>"
}

Response: 200 OK
{"detail": "Logged out successfully."}
```

#### User Management

```http
GET /api/users/me
Authorization: Bearer <access_token>

Response: 200 OK
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone_number": "+263771234567",
  "verification_status": "approved",
  "role": {
    "id": "uuid",
    "code": "resident",
    "name": "Resident"
  }
}
```

```http
PATCH /api/users/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "full_name": "Jane Doe",
  "address": "456 Oak Ave",
  "latitude": "17.8253",
  "longitude": "31.0336"
}

Response: 200 OK
{...updated profile...}
```

#### Incidents

```http
GET /api/incidents/
Authorization: Bearer <access_token>

Response: 200 OK
{
  "count": 42,
  "next": "...",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "title": "Suspicious Activity",
      "category": "suspicious_activity",
      "status": "pending",
      "severity": "blue",
      "latitude": "17.8252",
      "longitude": "31.0335",
      "created_at": "2024-01-15T09:30:00Z"
    }
  ]
}
```

```http
POST /api/incidents/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "neighborhood": "uuid",
  "title": "Suspicious Activity",
  "description": "Someone climbing fence at 2am",
  "category": "suspicious_activity",
  "severity": "blue",
  "latitude": "17.8252",
  "longitude": "31.0335",
  "address": "Main Street",
  "occurred_at": "2024-01-15T02:00:00Z"
}

Response: 201 Created
{...incident...}
```

```http
POST /api/incidents/{id}/verify/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "new_status": "verified"
}

Response: 200 OK
{...verified incident with verified_by and verified_at...}
```

```http
POST /api/incidents/{id}/upload_media/
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

file: <binary image/video/audio>
media_type: "image"
metadata: {"timestamp": "..."}

Response: 201 Created
{
  "id": "uuid",
  "incident": "uuid",
  "media_type": "image",
  "file": "https://...",
  "uploaded_by": "uuid",
  "uploaded_at": "2024-01-15T09:30:00Z"
}
```

### RBAC Matrix

| Endpoint | Resident | Block Captain | Coordinator | Police | Admin |
| --- | --- | --- | --- | --- | --- |
| POST /incidents | ✓ | ✓ | ✓ | ✓ | ✓ |
| PATCH /incidents/{id} | ✓* | ✓* | ✓* | ✓* | ✓* |
| POST /incidents/{id}/verify | ✗ | ✗ | ✓ | ✗ | ✓ |
| POST /incidents/{id}/assign | ✗ | ✗ | ✓ | ✗ | ✓ |
| POST /incidents/{id}/upload_media | ✓† | ✓† | ✓† | ✓† | ✓† |

*Only own incidents before verification
†Must be reporter, assigned, or admin

---

## Deployment Guide

### Prerequisites
- AWS account (or your cloud provider)
- Docker installed
- kubectl installed (for Kubernetes)
- Domain name configured

### Option 1: Docker Compose (Single Server)

```bash
# On your production server
git clone <repo-url>
cd neighbourhood-watch

# Configure environment
cp .env.example .env
# Edit .env with production settings

# Start services
docker compose -f docker-compose.yml up -d

# Verify
docker ps
curl http://localhost:8080/api/health/
```

### Option 2: Kubernetes (Scalable)

```bash
# Create namespace
kubectl create namespace nhwz

# Create secrets
kubectl create secret generic nhwz-secrets \
  --from-literal=DJANGO_SECRET_KEY='...' \
  --from-literal=DATABASE_URL='...' \
  -n nhwz

# Apply manifests
kubectl apply -f k8s/postgres.yaml -n nhwz
kubectl apply -f k8s/redis.yaml -n nhwz
kubectl apply -f k8s/api.yaml -n nhwz
kubectl apply -f k8s/frontend.yaml -n nhwz
kubectl apply -f k8s/nginx.yaml -n nhwz

# Monitor
kubectl get pods -n nhwz
kubectl logs -f deployment/api -n nhwz

# Scale
kubectl scale deployment/api --replicas=3 -n nhwz
```

### Environment Variables

**.env** for Docker:
```bash
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,example.com

# Database
DATABASE_URL=postgresql://nhwz:nhwz@localhost:5432/nhwz

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO
MINIO_ROOT_USER=nhwz
MINIO_ROOT_PASSWORD=your-secure-password

# AWS S3 (optional, instead of MinIO)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...

# Email (for OTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@example.com

# Frontend
VITE_API_BASE_URL=https://api.example.com
```

### SSL/TLS Configuration

For production, use Let's Encrypt with certbot:

```bash
# Generate certificate
certbot certonly --standalone -d api.example.com

# Configure Nginx to use certificate
# Update infra/nginx/default.conf with SSL settings

# Auto-renewal
certbot renew --dry-run
```

### Health Checks & Monitoring

```bash
# API health
curl http://localhost:8080/api/health/

# Database health
docker exec nhwz-postgres-1 pg_isready -U nhwz

# Redis health
docker exec nhwz-redis-1 redis-cli ping

# Logs
docker compose logs -f api
docker compose logs -f postgres
```

---

## Development Guide

### Project Structure

```
.
├── backend/                    # Django REST API
│   ├── apps/
│   │   ├── accounts/          # Authentication & users
│   │   ├── incidents/         # Incident management
│   │   └── ...
│   ├── config/
│   │   └── settings/          # Environment configs
│   ├── manage.py
│   └── requirements.txt
├── frontend/                   # React + Vite
│   ├── src/
│   │   ├── pages/             # Route pages
│   │   ├── components/        # UI components
│   │   └── api.js             # API client
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── infra/                     # Infrastructure
│   ├── docker/
│   │   └── backend.Dockerfile
│   └── nginx/
│       └── default.conf
├── docs/                      # Documentation
│   ├── PHASES_4_5_6_ROADMAP.md
│   └── ...
├── docker-compose.yml         # Local development stack
└── README.md
```

### Code Style & Conventions

**Python (Backend)**:
- Follow PEP 8 with Black formatter
- Type hints on functions
- Docstrings on models and services
- 100-character line limit

**JavaScript (Frontend)**:
- ESLint configuration included
- Functional components with hooks
- Tailwind CSS for styling
- File naming: kebab-case for components

### Testing

```bash
# Backend tests
cd backend
python manage.py test apps --settings=config.settings.test -v 2

# Run specific test class
python manage.py test apps.accounts.tests.test_models --settings=config.settings.test

# With coverage
pip install coverage
coverage run --source='.' manage.py test apps --settings=config.settings.test
coverage report

# Frontend tests (future)
cd ../frontend
npm test
```

### Adding New Features

1. **Backend**:
   - Add model to `apps/*/models.py`
   - Create migration: `python manage.py makemigrations`
   - Add serializer to `apps/*/serializers.py`
   - Add view to `apps/*/views.py`
   - Register URL in `apps/*/urls.py`
   - Write tests in `apps/*/tests/`

2. **Frontend**:
   - Create page in `src/pages/`
   - Create components in `src/components/`
   - Add API methods in `src/api.js`
   - Add route in `src/App.jsx`
   - Test locally at http://localhost:5173

### Debugging

**Backend**:
```python
# In Django shell
python manage.py shell --settings=config.settings.local

# Query models
from apps.accounts.models import User
User.objects.all()

# Debug views
import pdb; pdb.set_trace()  # Breakpoint
```

**Frontend**:
```javascript
// React DevTools browser extension recommended
console.log(state)  // Browser console
debugger  // Breakpoint in DevTools
```

**Docker Logs**:
```bash
docker compose logs -f api
docker compose logs -f postgres
docker exec nhwz-api-1 python manage.py shell
```

---

## FAQ

### Q: How do I reset the database?
A: Run `docker compose down -v && docker compose up --build` to remove all volumes and rebuild.

### Q: How do I create a test user?
A: 
```bash
docker exec nhwz-api-1 python manage.py shell
from apps.accounts.models import User, Role
role = Role.objects.get(code='resident')
User.objects.create_user(email='test@example.com', password='test123', full_name='Test User', phone_number='+263771234567', national_id='12345678A', role=role)
```

### Q: How do I access the PostgreSQL database directly?
A:
```bash
docker exec -it nhwz-postgres-1 psql -U nhwz -d nhwz
# SQL commands...
```

### Q: How do I deploy to AWS?
A: See the [Deployment Guide](#deployment-guide) section for Kubernetes instructions, which work on AWS ECS, GCP GKE, Azure AKS, etc.

### Q: What's the incident status workflow?
A: `PENDING` (reported) → `VERIFIED` (confirmed by coordinator) → `INVESTIGATING` (active response) → `RESOLVED` (issue fixed) → `CLOSED` (finalized)

### Q: Can residents see all incidents?
A: No. Residents see:
- Incidents they reported
- Incidents in their neighborhood
- Incidents assigned to them

### Q: How do I add new roles?
A:
```python
from apps.accounts.models import Role
Role.objects.create(code='new_role', name='New Role', is_system=True)
```

---

## Next Phases

### Phase 4: Geospatial Queries (Q1 2025)
- Radius searches with PostGIS
- Neighborhood geofencing
- Risk heatmaps
- Affected user detection

### Phase 5: Notification Engine (Q1 2025)
- Multi-channel dispatch (FCM, SMS, in-app)
- Celery async fanout
- Incident alerts
- SOS emergency contact notifications

### Phase 6: Frontend Polish (Q2 2025)
- React coordinator dashboard
- Flutter mobile app
- WebSocket real-time updates
- Maps integration

See `docs/PHASES_4_5_6_ROADMAP.md` for details.

---

## Support & Contributing

### Issues & Bug Reports
Report issues on GitHub with:
- Clear reproduction steps
- Expected vs actual behavior
- Environment details (OS, browser, Docker versions)

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add my feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Open a Pull Request

### Community
- **Slack**: #neighbourhood-watch (community channel)
- **Email**: support@example.com
- **Docs**: https://docs.example.com

---

## License & Security

### License
© 2024 Neighbourhood Watch Zimbabwe. All rights reserved.

### Security
- Report security issues to **security@example.com** (do NOT open public issues)
- All user data encrypted in transit (HTTPS)
- Passwords hashed with Django's PBKDF2
- JWT tokens expire after 1 hour
- Rate limiting on auth endpoints
- CORS configured for approved domains

### Privacy
- User location data stored securely
- Incident reports tied to verified users only
- GDPR-compliant data retention policies
- Data export available upon request

---

## Status & Roadmap

**Current**: Phase 3 - Production Ready  
**Tests**: 36/36 passing ✅  
**API**: 20+ endpoints implemented  
**Infrastructure**: Docker Compose + Kubernetes ready  

**Latest Updates**:
- ✅ Phase 3: Incident Reporting APIs complete
- ✅ Modern UI with Tailwind CSS
- ✅ Comprehensive API documentation
- 🚀 Next: Phase 4 (Geospatial Queries)

---

**Last Updated**: 2024-01  
**Maintained By**: Development Team  
**Support**: 24/7 Community Support
