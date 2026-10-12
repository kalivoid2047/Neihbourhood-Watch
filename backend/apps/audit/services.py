"""Audit logging helpers for user-facing workflows."""

from django.forms.models import model_to_dict

from .models import AuditLog


def _request_ip(request):
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _request_user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")


def snapshot_model(instance, fields=None):
    if instance is None:
        return None
    data = model_to_dict(instance, fields=fields)
    return {key: str(value) if value is not None else None for key, value in data.items()}


def create_audit_log(
    *,
    action,
    actor=None,
    entity=None,
    request=None,
    before=None,
    after=None,
    metadata=None,
):
    entity_type = entity.__class__.__name__ if entity is not None else ""
    entity_id = getattr(entity, "id", None)
    user = actor if getattr(actor, "is_authenticated", False) else None

    return AuditLog.objects.create(
        actor=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        before=before,
        after=after,
        metadata=metadata or {},
    )

