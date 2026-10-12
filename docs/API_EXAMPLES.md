# API Examples

Base URL:

```text
http://localhost:8000
```

## Register

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "resident@example.com",
    "password": "ZimSecurePass123!",
    "full_name": "Resident One",
    "phone_number": "+263771234567",
    "national_id": "63-123456A47",
    "address": "Avondale, Harare",
    "latitude": "-17.789123",
    "longitude": "31.044456"
  }'
```

Response:

```json
{
  "user": {
    "id": "uuid",
    "email": "resident@example.com",
    "full_name": "Resident One",
    "phone_number": "+263771234567",
    "verification_status": "resident"
  },
  "tokens": {
    "refresh": "jwt-refresh",
    "access": "jwt-access"
  },
  "otp": {
    "detail": "Registration OTP created.",
    "challenge_id": "uuid",
    "expires_at": "2026-06-03T12:00:00Z"
  }
}
```

## Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"resident@example.com","password":"ZimSecurePass123!"}'
```

## Refresh

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh":"jwt-refresh"}'
```

## Logout

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer jwt-access" \
  -H "Content-Type: application/json" \
  -d '{"refresh":"jwt-refresh"}'
```

## Request OTP

```bash
curl -X POST http://localhost:8000/api/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "resident@example.com",
    "purpose": "phone_verification",
    "channel": "sms"
  }'
```

## Verify OTP

```bash
curl -X POST http://localhost:8000/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "resident@example.com",
    "purpose": "phone_verification",
    "code": "123456"
  }'
```

## Forgot Password

```bash
curl -X POST http://localhost:8000/api/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"resident@example.com"}'
```

## Reset Password

```bash
curl -X POST http://localhost:8000/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "resident@example.com",
    "code": "123456",
    "new_password": "NewZimSecurePass123!"
  }'
```

## Current User Profile

```bash
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer jwt-access"
```

## Update Current User Profile

```bash
curl -X PATCH http://localhost:8000/api/users/me \
  -H "Authorization: Bearer jwt-access" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Resident Updated",
    "address": "Borrowdale, Harare",
    "phone_number": "+263771234568"
  }'
```

## Create Verification Request

```bash
curl -X POST http://localhost:8000/api/verification-requests \
  -H "Authorization: Bearer jwt-access" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Please verify my residence."}'
```

## Coordinator List Pending Requests

```bash
curl http://localhost:8000/api/coordinator/verification-requests \
  -H "Authorization: Bearer coordinator-jwt-access"
```

## Coordinator Approve Request

```bash
curl -X POST http://localhost:8000/api/coordinator/verification-requests/{id}/approve \
  -H "Authorization: Bearer coordinator-jwt-access" \
  -H "Content-Type: application/json" \
  -d '{"decision_reason":"Address confirmed."}'
```

## Coordinator Reject Request

```bash
curl -X POST http://localhost:8000/api/coordinator/verification-requests/{id}/reject \
  -H "Authorization: Bearer coordinator-jwt-access" \
  -H "Content-Type: application/json" \
  -d '{"decision_reason":"Address could not be confirmed."}'
```

## Postman Collection Notes

Create a Postman environment with:

```json
{
  "base_url": "http://localhost:8000",
  "access_token": "",
  "refresh_token": ""
}
```

Use `{{base_url}}/api/auth/login` to obtain tokens, then store `tokens.access` as `access_token` and `tokens.refresh` as `refresh_token`. Authenticated requests should use Bearer Token auth with `{{access_token}}`.

