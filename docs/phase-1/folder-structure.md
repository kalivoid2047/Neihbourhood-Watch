# Phase 1 Folder Structure

```text
.
|-- backend/
|   |-- manage.py
|   |-- config/
|   |   |-- settings/
|   |   |-- urls.py
|   |   |-- asgi.py
|   |   |-- wsgi.py
|   |   `-- celery.py
|   `-- apps/
|       |-- core/
|       |-- accounts/
|       |-- neighborhoods/
|       |-- incidents/
|       |-- notifications/
|       |-- sos/
|       |-- audit/
|       |-- sync/
|       `-- analytics/
|-- docs/
|   `-- phase-1/
|-- infra/
|   |-- docker/
|   `-- nginx/
|-- .github/
|   `-- workflows/
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
`-- README.md
```

## App Responsibilities

`core`
: Shared model primitives, health endpoint, schema endpoint, and production PostGIS foundation migration.

`accounts`
: Custom user model, role-based access control, verification workflow schema, device tokens, emergency contacts, and OTP challenge foundation.

`neighborhoods`
: Neighborhood boundaries, centroids, alert radius, and memberships.

`incidents`
: Incident reports and linked media evidence metadata.

`notifications`
: Push, SMS, and dashboard notification history.

`sos`
: Emergency sessions and GPS trail pings.

`audit`
: Actor, action, entity, before/after, IP, and metadata audit records.

`sync`
: Offline mutation queue, retry state, idempotency, and conflict tracking.

`analytics`
: Stored analytics snapshots for dashboard reporting.

