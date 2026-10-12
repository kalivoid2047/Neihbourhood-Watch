from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notifications_batch(self, notification_ids: list[str]) -> dict:
    """Deliver a batch of queued notifications via their respective providers.

    Each notification's channel determines which provider is used.  Failures
    are recorded on the notification row and do not abort remaining items.
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import NotificationDispatchService

    results = {"sent": 0, "failed": 0, "skipped": 0}
    notifications = Notification.objects.filter(
        pk__in=notification_ids,
        deleted_at__isnull=True,
    ).select_related("recipient")

    for notif in notifications:
        if notif.status not in (Notification.Status.QUEUED, Notification.Status.FAILED):
            results["skipped"] += 1
            continue

        provider_cls = NotificationDispatchService.PROVIDERS.get(notif.channel)
        if provider_cls is None:
            notif.status = Notification.Status.FAILED
            notif.error_message = f"Unknown channel: {notif.channel}"
            notif.save(update_fields=["status", "error_message", "updated_at", "last_modified_at"])
            results["failed"] += 1
            continue

        try:
            ok = provider_cls().send(notif)
            if ok:
                results["sent"] += 1
                if notif.channel == Notification.Channel.DASHBOARD:
                    from apps.core.broadcasting import broadcast_notification
                    broadcast_notification(notif)
            else:
                results["failed"] += 1
        except Exception as exc:  # noqa: BLE001
            notif.status = Notification.Status.FAILED
            notif.error_message = str(exc)
            notif.retry_count = notif.retry_count + 1
            notif.save(update_fields=["status", "error_message", "retry_count", "updated_at", "last_modified_at"])
            results["failed"] += 1

    return results


@shared_task
def retry_failed_notifications() -> dict:
    """Re-queue FAILED notifications from the last 24 hours (max 3 retries)."""
    from apps.notifications.models import Notification

    cutoff = timezone.now() - timedelta(hours=24)
    failed = Notification.objects.filter(
        status=Notification.Status.FAILED,
        created_at__gte=cutoff,
        retry_count__lt=3,
        deleted_at__isnull=True,
    )
    ids = list(failed.values_list("pk", flat=True))
    ids_str = [str(pk) for pk in ids]

    if ids_str:
        failed.update(status=Notification.Status.QUEUED)
        send_notifications_batch.delay(ids_str)

    return {"requeued": len(ids_str)}


@shared_task
def cleanup_old_notifications() -> dict:
    """Soft-delete notifications older than 90 days."""
    from apps.notifications.models import Notification

    cutoff = timezone.now() - timedelta(days=90)
    deleted = Notification.objects.filter(
        created_at__lt=cutoff,
        deleted_at__isnull=True,
    ).update(deleted_at=timezone.now())

    return {"deleted": deleted}
