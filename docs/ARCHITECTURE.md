# Architecture Overview

Neighbourhood Watch Zimbabwe is a modern, scalable platform designed with microservices principles and cloud-native deployment in mind.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  React SPA (5173)  │  Flutter Mobile  │  Web Browsers            │
└────────┬───────────┬──────────────────┬──────────────────────────┘
         │           │                  │
         └─────────────┬─────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   API Gateway (Nginx)                            │
│          Load Balancing, SSL/TLS, Static Files                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│              REST API (Django + DRF)                            │
├──────────────────────────────────────────────────────────────────┤
│  Auth          │  Incidents      │  Notifications               │
│  Users         │  Media          │  SOS                         │
│  Verification  │  Neighborhoods  │  Analytics                   │
│  Audit         │  Sync           │  (Future)                    │
└────────┬───────────┬──────────────┬───────────────────────────┬─┘
         │           │              │                           │
┌────────▼─┐   ┌─────▼──────┐   ┌──▼───────┐   ┌──────────────▼─┐
│ Auth     │   │ Business   │   │ Cache &  │   │ Async Tasks  │
│ Service  │   │ Logic      │   │ Sessions │   │ (Celery)     │
│ (JWT)    │   │            │   │ (Redis)  │   │              │
└────────┬─┘   └─────┬──────┘   └──┬───────┘   └──────────┬────┘
         │           │              │                      │
         └───┬───────┴──────────────┴──────────────────────┴─┐
             │                                                │
┌────────────▼────────────────────────────────────────────────▼──┐
│                      Data Layer                                 │
├────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  PostgreSQL     │  │   MongoDB    │  │  Elasticsearch  │  │
│  │  + PostGIS      │  │  (Future)    │  │  (Future)       │  │
│  │  (Users,        │  │              │  │                 │  │
│  │   Incidents,    │  │              │  │                 │  │
│  │   Audit Log)    │  │              │  │                 │  │
│  └─────────────────┘  └──────────────┘  └─────────────────┘  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                  External Services                              │
├────────────────────────────────────────────────────────────────┤
│  MinIO (S3)  │  Email (SMTP)  │  SMS (Twilio)  │  FCM          │
│  (Files)     │  (OTP, Alerts) │  (Alerts)      │  (Push)       │
└────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Frontend (React + Vite)

**Technology Stack**:
- React 18 with functional components and hooks
- React Router v6 for client-side routing
- Tailwind CSS for styling
- Lucide React for icons
- Axios for HTTP requests
- Vite for fast development and optimized builds

**Structure**:
```
frontend/src/
├── pages/                    # Route components
│   ├── home.jsx
│   ├── login.jsx
│   ├── register.jsx
│   ├── profile.jsx
│   ├── incidents.jsx
│   └── coordinator.jsx
├── components/              # Reusable components
│   ├── ui.jsx              # Design system (Button, Card, etc.)
│   └── layout.jsx          # Header, Footer, Page layouts
├── styles/
│   └── globals.css         # Tailwind imports
├── api.js                  # HTTP client with JWT auth
└── App.jsx                 # Main router
```

**Features**:
- Responsive design (mobile, tablet, desktop)
- Progressive enhancement
- Offline capability (future: service workers)
- Real-time updates (future: WebSockets)

### 2. Backend API (Django + DRF)

**Technology Stack**:
- Django 5.2 with async support
- Django REST Framework for API development
- SimpleJWT for JWT token management
- Django Channels for WebSockets (future)
- Celery for async task processing
- Gunicorn as WSGI server

**App Architecture**:

Each Django app follows this structure:
```
apps/[app_name]/
├── models.py          # Database models
├── serializers.py     # DRF serializers (request/response validation)
├── views.py           # API endpoints (ViewSets, APIViews)
├── urls.py            # URL routing
├── permissions.py     # RBAC/permission classes
├── services.py        # Business logic (not tied to HTTP)
├── migrations/        # Database migrations
└── tests/
    ├── test_models.py
    ├── test_api.py
    └── test_services.py
```

**Request-Response Cycle**:
```
HTTP Request
    ↓
Nginx (reverse proxy, static files)
    ↓
Gunicorn (WSGI server)
    ↓
Django Middleware (auth, CORS, etc.)
    ↓
Django URL Router
    ↓
DRF Authentication (JWT verification)
    ↓
DRF Permissions (RBAC checks)
    ↓
DRF Throttling (rate limiting)
    ↓
Serializer (input validation)
    ↓
View (business logic)
    ↓
Service Layer (core domain logic)
    ↓
Database ORM (queries)
    ↓
Response Serializer (output formatting)
    ↓
HTTP Response
```

### 3. Database (PostgreSQL + PostGIS)

**Schema Design**:
- UUID primary keys for all tables
- Soft deletion (`deleted_at` field)
- Audit timestamps (`created_at`, `updated_at`, `last_modified_at`)
- Indexes on frequently queried fields
- Foreign keys with proper constraints

**Key Tables**:
- `accounts_user` - User profiles and authentication
- `accounts_role` - RBAC roles
- `accounts_verification_request` - Verification workflow
- `incidents_incident` - Incident reports
- `incidents_incident_media` - Evidence attachments
- `neighborhoods_neighborhood` - Geographic zones
- `audit_audit_log` - Activity tracking

**PostGIS Extensions** (Production only):
- `geography` columns for coordinates
- GiST indexes for spatial queries
- Functions: ST_DWithin, ST_Contains, etc.

### 4. Caching & Sessions (Redis)

**Purpose**:
- JWT token blacklist (logout)
- Session storage
- Rate limiting counters
- Celery task queue

**Data Structure**:
```
Redis DB 0: Cache & Sessions
Redis DB 1: Celery Task Queue
Redis DB 2: Rate Limiting
```

### 5. Task Queue (Celery)

**Async Tasks**:
- Send OTP emails
- Send notifications
- Process media uploads
- Generate analytics
- Cleanup stale data

**Configuration**:
```python
# Broker: Redis
# Result backend: Redis
# Retry policy: Exponential backoff
```

### 6. File Storage (MinIO)

**Purpose**:
- Store incident media (images, videos)
- Store user profile photos
- Backup documents

**Structure**:
```
nhwz-bucket/
├── profiles/
│   └── {user_id}/
│       └── photo.jpg
├── incident-evidence/
│   └── 2024/01/
│       └── {incident_id}/
│           ├── image_1.jpg
│           ├── video_1.mp4
│           └── audio_1.m4a
```

---

## Data Flow Examples

### User Registration Flow

```
1. Frontend
   └─→ POST /api/auth/register
       ├─ Input validation
       └─ Hash password (Django)

2. Backend
   ├─ Serialize & validate registration data
   ├─ Check for duplicates (email, phone, ID)
   ├─ Create User + DeviceToken
   ├─ Generate OTP challenge (SMS)
   ├─ Create audit log
   ├─ Generate JWT tokens
   └─ Return user + tokens + OTP info

3. Frontend
   ├─ Store JWT tokens in localStorage
   ├─ Redirect to OTP verification
   └─ Display "Verify your phone"

4. User enters OTP code
   └─→ POST /api/auth/verify-otp

5. Backend
   ├─ Verify OTP code (compare hashed)
   ├─ Mark user.otp_verified_at
   ├─ Create audit log
   └─ Return success

6. Frontend
   ├─ Redirect to dashboard
   └─ User logged in ✓
```

### Incident Report Flow

```
1. Frontend (Authenticated User)
   └─→ POST /api/incidents/
       ├─ Title, description, category, severity
       ├─ Location (lat/lon)
       └─ Occurred at timestamp

2. Backend - Create Incident
   ├─ Validate request (DRF serializer)
   ├─ Check user permissions
   ├─ Set reporter = current user
   ├─ Set status = PENDING
   ├─ Save incident
   ├─ Create audit log ("incident_created")
   ├─ Trigger Celery task: notify_neighborhood()
   └─ Return incident + 201 Created

3. Backend - Async Task (Celery)
   ├─ Find users in neighborhood
   ├─ Filter by notification preferences
   ├─ Send FCM push + email notifications
   └─ Log notification delivery

4. Frontend (Other Users in Neighborhood)
   ├─ Receive push notification
   ├─ Refresh incidents list
   └─ See new incident

5. Coordinator Reviews Incident
   └─→ POST /api/incidents/{id}/verify/
       ├─ Check permission (coordinator role)
       ├─ Update incident.status = VERIFIED
       ├─ Set verified_by = current user
       ├─ Set verified_at = now
       ├─ Create audit log ("incident_verified")
       └─ Return incident

6. Later: Incident Status Transitions
   └─→ PENDING → VERIFIED → INVESTIGATING → RESOLVED → CLOSED
       ├─ Only coordinators/admins can transition
       ├─ Certain transitions forbidden (e.g., CLOSED → VERIFIED)
       ├─ Each transition creates audit log
       └─ Notify affected users
```

### Media Upload Flow

```
1. Frontend
   └─→ POST /api/incidents/{id}/upload_media/
       ├─ Multipart form data
       ├─ File (image/video/audio)
       ├─ Media type (image|video|audio)
       └─ Optional metadata

2. Backend - Media Upload
   ├─ Check file size (<100MB)
   ├─ Validate MIME type
   ├─ Upload to MinIO
   ├─ Generate checksum
   ├─ Create IncidentMedia record
   ├─ Create audit log
   └─ Return media metadata

3. Backend - File Storage (MinIO)
   ├─ Store in S3 bucket
   ├─ Generate signed URL (valid 1 hour)
   └─ Return file location

4. Frontend - Display Media
   ├─ Fetch media list from API
   ├─ Display thumbnails
   ├─ On click: fetch signed URL
   └─ Open in lightbox/viewer
```

---

## Security Architecture

### Authentication Flow

```
1. User logs in
   └─→ POST /api/auth/login
       ├─ Validate email + password
       ├─ Generate access token (1 hour)
       ├─ Generate refresh token (7 days)
       └─ Return both tokens

2. Frontend stores tokens
   ├─ Access token in memory (cleared on refresh)
   ├─ Refresh token in localStorage
   └─ Include access token in all API requests

3. Backend validates JWT
   ├─ Verify signature (Django secret key)
   ├─ Check expiry
   ├─ Extract user ID
   └─ Fetch user + role

4. Token refresh
   └─→ POST /api/auth/refresh
       ├─ Verify refresh token
       ├─ Generate new access token
       ├─ Optionally rotate refresh token
       └─ Return new tokens

5. Logout
   └─→ POST /api/auth/logout
       ├─ Add refresh token to blacklist (Redis)
       ├─ Clear frontend token
       └─ Revoke access
```

### Permission Layers

```
Layer 1: HTTP Auth
├─ No Bearer token → 401 Unauthorized
└─ Invalid token → 401 Unauthorized

Layer 2: User Permission
├─ Inactive user → 403 Forbidden
└─ User not found → 401 Unauthorized

Layer 3: Resource Permission
├─ No access to incident → 403 Forbidden
├─ Only coordinator can verify → 403 Forbidden
└─ Assigned to different user → 403 Forbidden

Layer 4: Business Logic
├─ Cannot transition from PENDING to CLOSED
├─ Cannot verify already verified incident
└─ Media file too large
```

### Data Security

- **In Transit**: HTTPS/TLS (all traffic)
- **At Rest**: Database encryption (AWS KMS, etc.)
- **Passwords**: PBKDF2 hashing + salt
- **Secrets**: Environment variables, not in code
- **API Keys**: Rotation every 90 days
- **Token Expiry**: Access tokens 1 hour, refresh tokens 7 days

---

## Deployment Architecture

### Local Development

```
Developer Laptop
├── Frontend (npm run dev) → http://localhost:5173
├── Backend (manage.py runserver) → http://localhost:8000
├── PostgreSQL (local or Docker)
├── Redis (local or Docker)
└── MinIO (Docker)
```

### Docker Compose (Staging/Demo)

```
Single Host (docker-compose.yml)
├── nginx (reverse proxy)
├── api (Django Gunicorn)
├── postgres (PostgreSQL)
├── redis (Redis)
└── minio (File storage)
```

### Kubernetes (Production)

```
Kubernetes Cluster (AWS EKS, GCP GKE, Azure AKS)
├── API Pod × 3 (replicas, auto-scaling)
├── PostgreSQL StatefulSet × 2 (primary + replica)
├── Redis Cluster (3+ nodes)
├── MinIO Cluster (4+ nodes)
├── Nginx Ingress (load balancing)
├── RabbitMQ (message queue for Celery)
└── Prometheus + Grafana (monitoring)
```

---

## Performance Optimization

### Frontend
- **Code splitting** by route
- **Image optimization** (WebP, lazy loading)
- **CSS purging** (only used Tailwind)
- **API response caching** (stale-while-revalidate)

### Backend
- **Database indexes** on frequently queried fields
- **Query optimization** (select_related, prefetch_related)
- **Caching layer** (Redis for sessions, roles, permissions)
- **Pagination** (default 20 items per page)
- **Rate limiting** (1000 requests per minute)

### Infrastructure
- **Load balancing** (Nginx round-robin or cloud LB)
- **Auto-scaling** (based on CPU/memory)
- **CDN** for static files
- **DB connection pooling** (PgBouncer)

---

## Monitoring & Logging

### Logs
- **Application logs**: Django logging to stdout + file
- **Access logs**: Nginx access.log + error.log
- **Database logs**: PostgreSQL query logs (slow query log)
- **Aggregation**: ELK Stack or CloudWatch

### Metrics
- **Application**: Response time, error rate, throughput
- **Database**: Query time, connections, cache hit ratio
- **Infrastructure**: CPU, memory, disk, network I/O
- **Tool**: Prometheus + Grafana

### Alerts
- **Error rate** >5% → Page on-call
- **Response time** P95 >2s → Alert
- **Database connections** >80 → Alert
- **Disk space** <10% → Alert

---

## Future Architecture Enhancements

### Phase 4: Real-time Updates
- WebSockets for live incident notifications
- Server-Sent Events (SSE) fallback
- Real-time collaboration on incident details

### Phase 5: Messaging
- Message queue: RabbitMQ or AWS SQS
- Message broker: Apache Kafka for event streaming
- Event-driven architecture

### Phase 6: Analytics
- Data warehouse: BigQuery or Snowflake
- BI tool: Tableau or Looker
- Real-time analytics dashboard

### Phase 7: Machine Learning
- Anomaly detection: Unusual incident patterns
- Classification: Auto-categorize incidents
- Prediction: Forecast high-risk areas/times

---

## References

- [Django Architecture Best Practices](https://docs.djangoproject.com/)
- [React Design Patterns](https://react.dev/)
- [Microservices Architecture](https://microservices.io/)
- [The Twelve-Factor App](https://12factor.net/)
- [OWASP Security Best Practices](https://owasp.org/)
