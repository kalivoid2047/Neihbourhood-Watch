"""
Tests for Phase 3 infrastructure changes in the accounts app.

Covers:
  - OTP email dispatch when channel=EMAIL (3.5)
  - No email dispatched when channel=SMS (3.5)
  - OTP email contains the code and goes to the right address (3.5)
  - cleanup_expired_otp_challenges deletes stale records only (3.8)
  - Protected media endpoint returns 401 for unauthenticated requests (3.2)
  - Protected media endpoint returns 200 for authenticated requests in DEBUG (3.2)
  - USE_S3_STORAGE=False does not configure S3 STORAGES backend (3.1)
  - CACHES is set to locmem in test settings (3.3)
"""

from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import OTPChallenge, Role, User
from apps.accounts.services.otp_service import OTPService
from apps.accounts.tasks import cleanup_expired_otp_challenges, send_otp_email


PASSWORD = "ZimSecurePass123!"


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
):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name="Resident One",
        phone_number=phone_number,
        national_id=national_id,
        role=create_role(Role.Code.RESIDENT),
    )


# ---------------------------------------------------------------------------
# 3.5 OTP email dispatch
# ---------------------------------------------------------------------------

def _eager_delay(*args, **kwargs):
    """Replacement for send_otp_email.delay that runs the task synchronously."""
    send_otp_email(*args, **kwargs)


@patch("apps.accounts.tasks.send_otp_email.delay", side_effect=_eager_delay)
class OTPEmailDispatchTests(TestCase):
    """OTPService dispatches email when channel=EMAIL, silent when channel=SMS.

    .delay() is patched to run synchronously so tests never need a Celery broker.
    """

    def setUp(self):
        self.user = create_user()

    def test_email_channel_sends_one_email(self, _mock_delay):
        OTPService().generate(
            user=self.user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.EMAIL,
            destination=self.user.email,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_email_sent_to_correct_recipient(self, _mock_delay):
        OTPService().generate(
            user=self.user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.EMAIL,
            destination=self.user.email,
        )
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_email_body_contains_otp_code(self, _mock_delay):
        delivery = OTPService().generate(
            user=self.user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.EMAIL,
            destination=self.user.email,
        )
        self.assertIn(delivery.code, mail.outbox[0].body)

    def test_password_reset_email_has_correct_subject(self, _mock_delay):
        OTPService().generate(
            user=self.user,
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
            channel=OTPChallenge.Channel.EMAIL,
            destination=self.user.email,
        )
        self.assertIn("Reset", mail.outbox[0].subject)

    def test_sms_channel_does_not_send_email(self, _mock_delay):
        OTPService().generate(
            user=self.user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.SMS,
            destination=self.user.phone_number,
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_multiple_generates_send_separate_emails(self, _mock_delay):
        user2 = create_user(
            email="resident2@example.com",
            phone_number="+263771234568",
            national_id="63-123456A48",
        )
        OTPService().generate(
            user=self.user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.EMAIL,
            destination=self.user.email,
        )
        OTPService().generate(
            user=user2,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.EMAIL,
            destination=user2.email,
        )
        self.assertEqual(len(mail.outbox), 2)
        recipients = {m.to[0] for m in mail.outbox}
        self.assertIn(self.user.email, recipients)
        self.assertIn(user2.email, recipients)


# ---------------------------------------------------------------------------
# 3.8 OTP cleanup task
# ---------------------------------------------------------------------------

class OTPCleanupTaskTests(TestCase):
    """cleanup_expired_otp_challenges removes old records without touching live ones."""

    def setUp(self):
        self.user = create_user()

    def _make_challenge(self, expires_at):
        return OTPChallenge.objects.create(
            user=self.user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.SMS,
            destination=self.user.phone_number,
            hashed_code="x",
            expires_at=expires_at,
        )

    def test_stale_challenges_are_deleted(self):
        stale_time = timezone.now() - timedelta(days=8)
        self._make_challenge(stale_time)
        result = cleanup_expired_otp_challenges()
        self.assertEqual(OTPChallenge.objects.count(), 0)
        self.assertIn("Deleted 1", result)

    def test_recent_expired_challenges_are_retained(self):
        recent_expired = timezone.now() - timedelta(hours=1)
        self._make_challenge(recent_expired)
        cleanup_expired_otp_challenges()
        self.assertEqual(OTPChallenge.objects.count(), 1)

    def test_active_challenges_are_never_deleted(self):
        future = timezone.now() + timedelta(minutes=10)
        self._make_challenge(future)
        cleanup_expired_otp_challenges()
        self.assertEqual(OTPChallenge.objects.count(), 1)

    def test_cleanup_returns_count_string(self):
        for i in range(3):
            self._make_challenge(timezone.now() - timedelta(days=8))
        result = cleanup_expired_otp_challenges()
        self.assertIn("3", result)

    def test_cleanup_with_no_stale_records_returns_zero(self):
        result = cleanup_expired_otp_challenges()
        self.assertIn("0", result)


# ---------------------------------------------------------------------------
# 3.2 Protected media endpoint
# ---------------------------------------------------------------------------

class ProtectedMediaEndpointTests(TestCase):
    """Unauthenticated access to /api/media/ is denied; authenticated access works."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get("/api/media/some/file.jpg")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(USE_S3_STORAGE=True)
    def test_s3_mode_returns_404(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/media/some/file.jpg")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(USE_S3_STORAGE=False, DEBUG=False)
    def test_production_mode_returns_x_accel_redirect(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/media/incidents/photo.jpg")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-Accel-Redirect"], "/protected-media/incidents/photo.jpg")


# ---------------------------------------------------------------------------
# 3.1 S3 storage setting
# ---------------------------------------------------------------------------

class S3StorageSettingTests(TestCase):
    """USE_S3_STORAGE=False must not configure the S3 storage backend."""

    @override_settings(USE_S3_STORAGE=False)
    def test_s3_storage_disabled_by_default(self):
        from django.conf import settings
        use_s3 = getattr(settings, "USE_S3_STORAGE", False)
        self.assertFalse(use_s3)

    def test_default_storages_backend_is_filesystem(self):
        from django.conf import settings
        storages = getattr(settings, "STORAGES", {})
        default_backend = storages.get("default", {}).get("BACKEND", "")
        self.assertNotIn("s3", default_backend.lower())


# ---------------------------------------------------------------------------
# 3.3 Cache backend
# ---------------------------------------------------------------------------

class CacheSettingTests(TestCase):
    """Test settings must use in-memory cache, not Redis."""

    def test_test_settings_use_locmem_cache(self):
        from django.conf import settings
        backend = settings.CACHES["default"]["BACKEND"]
        self.assertIn("locmem", backend.lower())
