from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import models

from apps.audit.models import AuditEvent



def _normalize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, models.Model):
        return str(value.pk)
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    return value



def record_audit_event(*, entity, action: str, actor=None, before_data=None, after_data=None, request_id: str = ""):
    return AuditEvent.objects.create(
        entity_type=entity._meta.label_lower,
        entity_id=entity.pk,
        action=action,
        actor=actor,
        request_id=request_id,
        before_data=_normalize_value(before_data or {}),
        after_data=_normalize_value(after_data or {}),
    )
