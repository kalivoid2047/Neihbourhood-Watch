from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.models import OTPChallenge, Role, User
from apps.audit.models import AuditLog

# Suppress the Celery task dispatch in all auth API tests — these tests verify API
# behaviour and audit logging, not email delivery. Patching avoids needing a broker.
_patch_otp_email = patch("apps.accounts.tasks.send_otp_email.delay")
_patch_otp_email.start()


PASSWORD = "ZimSecurePass123!"
NEW_PASSWORD = "NewZimSecurePass123!"


def create_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def create_user(
    *,
    email="resident@example.com",
    phone_number="+263771234567",
    national_id="63-123456A47",
    role_code=Role.Code.RESIDENT,
    password=PASSWORD,
):
    return User.objects.create_user(
        email=email,
        password=password,
        full_name="Resident One",
        phone_number=phone_number,
        national_id=national_id,
        role=create_role(role_code),
    )


class AuthenticationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_creates_resident_tokens_otp_and_audit_log(self):
        response = self.client.post(
            "/api/auth/register",
            {
                "email": "new@example.com",
                "password": PASSWORD,
                "full_name": "New Resident",
                "phone_number": "+263771234568",
                "national_id": "63-123456A48",
                "address": "Avondale, Harare",
                "latitude": "-17.789123",
                "longitude": "31.044456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.json()["tokens"])
        self.assertIn("debug_code", response.json()["otp"])
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.role.code, Role.Code.RESIDENT)
        self.assertTrue(OTPChallenge.objects.filter(user=user, purpose=OTPChallenge.Purpose.REGISTRATION).exists())
        self.assertTrue(AuditLog.objects.filter(actor=user, action="registration").exists())

    def test_login_returns_tokens_and_writes_audit_log(self):
        user = create_user()

        response = self.client.post(
            "/api/auth/login",
            {"email": user.email, "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json()["tokens"])
        self.assertIn("refresh", response.json()["tokens"])
        self.assertTrue(AuditLog.objects.filter(actor=user, action="login").exists())

    def test_refresh_rotates_token(self):
        user = create_user()
        login_response = self.client.post(
            "/api/auth/login",
            {"email": user.email, "password": PASSWORD},
            format="json",
        )

        response = self.client.post(
            "/api/auth/refresh",
            {"refresh": login_response.json()["tokens"]["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    def test_logout_blacklists_refresh_token_and_writes_audit_log(self):
        user = create_user()
        login_response = self.client.post(
            "/api/auth/login",
            {"email": user.email, "password": PASSWORD},
            format="json",
        )
        tokens = login_response.json()["tokens"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(
            "/api/auth/logout",
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BlacklistedToken.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(actor=user, action="logout").exists())

    def test_request_and_verify_otp_updates_verification_timestamp(self):
        user = create_user()

        request_response = self.client.post(
            "/api/auth/request-otp",
            {
                "identifier": user.email,
                "purpose": OTPChallenge.Purpose.PHONE_VERIFICATION,
                "channel": OTPChallenge.Channel.SMS,
            },
            format="json",
        )
        code = request_response.json()["debug_code"]
        verify_response = self.client.post(
            "/api/auth/verify-otp",
            {
                "identifier": user.email,
                "purpose": OTPChallenge.Purpose.PHONE_VERIFICATION,
                "code": code,
            },
            format="json",
        )

        self.assertEqual(request_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertIsNotNone(user.otp_verified_at)

    def test_forgot_and_reset_password_changes_password_and_writes_audit(self):
        user = create_user()
        forgot_response = self.client.post(
            "/api/auth/forgot-password",
            {"email": user.email},
            format="json",
        )

        reset_response = self.client.post(
            "/api/auth/reset-password",
            {
                "email": user.email,
                "code": forgot_response.json()["debug_code"],
                "new_password": NEW_PASSWORD,
            },
            format="json",
        )

        self.assertEqual(forgot_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertTrue(AuditLog.objects.filter(actor=user, action="password_reset_requested").exists())
        self.assertTrue(AuditLog.objects.filter(actor=user, action="password_reset").exists())

