"""Database-backed OTP service with provider-friendly boundaries."""

from dataclasses import dataclass
import logging
from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import OTPChallenge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OTPDelivery:
    challenge: OTPChallenge
    code: str
    expires_at: object


class OTPService:
    def __init__(self, *, ttl_minutes=None, max_attempts=None, code_length=None):
        self.ttl_minutes = ttl_minutes or getattr(settings, "OTP_TTL_MINUTES", 10)
        self.max_attempts = max_attempts or getattr(settings, "OTP_MAX_ATTEMPTS", 5)
        self.code_length = code_length or getattr(settings, "OTP_LENGTH", 6)

    def generate(self, *, user, purpose, channel, destination) -> OTPDelivery:
        code = self._generate_code()
        expires_at = timezone.now() + timedelta(minutes=self.ttl_minutes)
        challenge = OTPChallenge.objects.create(
            user=user,
            purpose=purpose,
            channel=channel,
            destination=destination,
            hashed_code=make_password(code),
            expires_at=expires_at,
        )
        if channel == OTPChallenge.Channel.EMAIL:
            from apps.accounts.tasks import send_otp_email
            try:
                send_otp_email.delay(destination, code, purpose, expires_at.isoformat())
            except Exception:
                # A mail/broker outage must not fail the request; the challenge is
                # saved, so the user can ask for the code to be sent again.
                logger.exception("Could not queue OTP email for challenge %s", challenge.pk)
        return OTPDelivery(challenge=challenge, code=code, expires_at=expires_at)

    def verify(self, *, user, purpose, code) -> OTPChallenge:
        challenge = (
            OTPChallenge.objects.filter(
                user=user,
                purpose=purpose,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            raise ValidationError("No active OTP challenge was found.")

        now = timezone.now()
        if challenge.expires_at <= now:
            raise ValidationError("OTP code has expired.")

        if challenge.attempts >= self.max_attempts:
            raise ValidationError("Maximum OTP verification attempts exceeded.")

        challenge.attempts += 1
        if not check_password(code, challenge.hashed_code):
            challenge.save(update_fields=["attempts", "updated_at", "last_modified_at"])
            raise ValidationError("Invalid OTP code.")

        challenge.consumed_at = now
        challenge.save(
            update_fields=[
                "attempts",
                "consumed_at",
                "updated_at",
                "last_modified_at",
            ]
        )
        return challenge

    def _generate_code(self) -> str:
        upper_bound = 10**self.code_length
        return f"{secrets.randbelow(upper_bound):0{self.code_length}d}"

