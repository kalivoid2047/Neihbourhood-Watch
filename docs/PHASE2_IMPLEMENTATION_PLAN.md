# Phase 2 Implementation Plan

## Existing Architecture Review

The repository contains a backend-first Django architecture under `backend/` with environment-driven settings in `config/settings`. Django REST Framework, Simple JWT, CORS, filtering, PostgreSQL/PostGIS configuration, Redis configuration, Docker Compose, Nginx, and GitHub Actions are already present.

The project is organized into focused Django apps:

- `core`: shared model primitives, health endpoint, manual OpenAPI endpoint, conditional PostGIS foundation migration.
- `accounts`: custom user model, role and permission model, verification request model, device tokens, emergency contacts, OTP challenge model, role seeding command.
- `neighborhoods`: neighborhood and membership data.
- `incidents`: incident and evidence metadata.
- `notifications`: notification history model.
- `sos`: SOS session and location ping models.
- `audit`: audit log model.
- `sync`: offline sync queue model.
- `analytics`: analytics snapshot model.

The existing code uses UUID primary keys, timestamp fields, soft deletion, and first-pass indexes. The current API surface before Phase 2 was limited to API metadata, health, schema, and legacy Simple JWT token endpoints.

## Existing Models Review

The Phase 1 schema already supports the Phase 2 use cases:

- `accounts.User` stores identity, phone, national ID, address, coordinates, profile image, role, verification status, and OTP verification timestamp.
- `accounts.Role`, `accounts.Permission`, and `accounts.RolePermission` provide the RBAC foundation.
- `accounts.VerificationRequest` supports pending, approved, and rejected resident verification workflow states.
- `accounts.OTPChallenge` stores hashed OTPs, purpose, delivery channel, expiry, consumption time, and attempt count.
- `audit.AuditLog` stores actor, action, entity, IP, user agent, before/after snapshots, and metadata.

No database schema change is required for Phase 2 because the foundation already contains the necessary entities.

## Gaps Identified

- No registration, login, logout, refresh aliases, password reset, or OTP APIs existed under `/api/auth`.
- No profile API existed at `/api/users/me`.
- Verification requests existed as a model but had no resident or coordinator APIs.
- Role checks existed for capability strings, but coordinator endpoint role-code protection was not yet implemented.
- OTP generation and verification were not abstracted into a service.
- Audit log records were not created by user-facing workflows.
- The manual OpenAPI endpoint did not describe Phase 2 endpoints.
- Tests covered only Phase 1 model/health/schema behavior.

## Proposed Implementation Plan

1. Add service abstractions:
   - `apps.accounts.services.otp_service.OTPService`
   - `apps.audit.services.create_audit_log`
2. Add scoped throttles for registration, login, OTP, and password reset flows.
3. Expand account serializers for registration, login, OTP, password reset, profile updates, and verification decisions.
4. Add role-code DRF permission enforcement for coordinator-only workflows.
5. Implement endpoints:
   - `POST /api/auth/register`
   - `POST /api/auth/login`
   - `POST /api/auth/refresh`
   - `POST /api/auth/logout`
   - `POST /api/auth/request-otp`
   - `POST /api/auth/verify-otp`
   - `POST /api/auth/forgot-password`
   - `POST /api/auth/reset-password`
   - `GET /api/users/me`
   - `PATCH /api/users/me`
   - `POST /api/verification-requests`
   - `GET /api/coordinator/verification-requests`
   - `POST /api/coordinator/verification-requests/{id}/approve`
   - `POST /api/coordinator/verification-requests/{id}/reject`
6. Update manual OpenAPI documentation with request examples and authentication metadata.
7. Add API examples and next-phase roadmap documents.
8. Add tests for authentication, OTP, password reset, profile, verification workflow, audit logging, and access restrictions.
9. Run `pytest`, `python backend/manage.py check`, `python backend/manage.py makemigrations --check --dry-run`, and `python backend/manage.py test apps`.

## Architecture Decisions

- Keep Simple JWT as the token engine and expose Phase 2 aliases under `/api/auth/*` while retaining the legacy Phase 1 `/api/token/*` endpoints.
- Store OTPs in the existing `OTPChallenge` table using Django password hashers so plaintext codes are never persisted.
- Return `debug_code` only when `OTP_EXPOSE_DEBUG_CODES` is enabled for local/test workflows until SMS/email providers are integrated.
- Use service functions for audit logging and OTP handling to keep view code thin and make provider integrations easier later.
- Enforce coordinator verification actions with role-code permissions so tests and operational behavior are explicit even before a richer policy engine is introduced.

