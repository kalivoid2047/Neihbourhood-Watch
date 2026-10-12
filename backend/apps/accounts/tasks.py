"""Celery tasks for the accounts app."""

from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone


_OTP_SUBJECTS = {
    "registration": "Your Neighbourhood Watch verification code",
    "password_reset": "Reset your Neighbourhood Watch password",
    "phone_verification": "Your Neighbourhood Watch code",
}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_otp_email(self, recipient_email: str, code: str, purpose: str, expires_at_str: str):
    """Send an OTP code to the given email address.

    Retries up to 3 times with a 30-second delay on SMTP failure.
    """
    subject = _OTP_SUBJECTS.get(purpose, "Your one-time code")
    body = (
        f"Your one-time code is: {code}\n\n"
        f"This code expires at {expires_at_str} (UTC).\n\n"
        "Do not share this code with anyone."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def cleanup_expired_otp_challenges():
    """Delete OTP challenge records that expired more than 7 days ago.

    Scheduled daily at 02:00 via Celery Beat. Keeps the otp_challenge table
    from growing unboundedly while retaining recent history for debugging.
    """
    from apps.accounts.models import OTPChallenge

    cutoff = timezone.now() - timedelta(days=7)
    # SoftDeleteQuerySet.delete() calls update() which returns a plain int, not a (count, {}) tuple.
    deleted = OTPChallenge.objects.filter(expires_at__lt=cutoff).delete()
    if isinstance(deleted, tuple):
        deleted = deleted[0]
    return f"Deleted {deleted} expired OTP challenges."
