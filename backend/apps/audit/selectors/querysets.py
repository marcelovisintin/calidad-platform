from __future__ import annotations

from uuid import UUID

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.audit.models import AuditEvent

ORDERING_FIELDS = {
    "created_at",
    "-created_at",
    "action",
    "-action",
    "entity_type",
    "-entity_type",
}



def build_audit_event_queryset():
    return AuditEvent.objects.select_related("actor").all()



def _parse_uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None



def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}



def _is_falsy(value: str) -> bool:
    return str(value).strip().lower() in {"0", "false", "no", "off"}



def _apply_created_from(queryset, raw_value: str):
    parsed_datetime = parse_datetime(raw_value)
    if parsed_datetime is not None:
        return queryset.filter(created_at__gte=parsed_datetime)

    parsed_date = parse_date(raw_value)
    if parsed_date is not None:
        return queryset.filter(created_at__date__gte=parsed_date)

    return queryset



def _apply_created_to(queryset, raw_value: str):
    parsed_datetime = parse_datetime(raw_value)
    if parsed_datetime is not None:
        return queryset.filter(created_at__lte=parsed_datetime)

    parsed_date = parse_date(raw_value)
    if parsed_date is not None:
        return queryset.filter(created_at__date__lte=parsed_date)

    return queryset



def apply_audit_event_filters(queryset, params):
    if entity_type := params.get("entity_type"):
        queryset = queryset.filter(entity_type__iexact=entity_type.strip())

    if source_app := params.get("source_app"):
        queryset = queryset.filter(entity_type__istartswith=f"{source_app.strip().lower()}.")

    if entity_id := params.get("entity_id"):
        parsed_uuid = _parse_uuid(entity_id)
        queryset = queryset.filter(entity_id=parsed_uuid) if parsed_uuid else queryset.none()

    if action := params.get("action"):
        queryset = queryset.filter(action__iexact=action.strip())

    if actor := params.get("actor"):
        parsed_uuid = _parse_uuid(actor)
        if parsed_uuid is not None:
            queryset = queryset.filter(actor_id=parsed_uuid)
        else:
            queryset = queryset.filter(actor__username__iexact=actor.strip())

    if request_id := params.get("request_id"):
        queryset = queryset.filter(request_id__iexact=request_id.strip())

    if has_request_id := params.get("has_request_id"):
        if _is_truthy(has_request_id):
            queryset = queryset.exclude(request_id="")
        elif _is_falsy(has_request_id):
            queryset = queryset.filter(request_id="")

    if created_from := params.get("created_from"):
        queryset = _apply_created_from(queryset, created_from)

    if created_to := params.get("created_to"):
        queryset = _apply_created_to(queryset, created_to)

    if term := params.get("search"):
        scoped_filter = (
            Q(entity_type__icontains=term)
            | Q(action__icontains=term)
            | Q(request_id__icontains=term)
            | Q(actor__username__icontains=term)
            | Q(actor__email__icontains=term)
        )
        parsed_uuid = _parse_uuid(term)
        if parsed_uuid is not None:
            scoped_filter |= Q(entity_id=parsed_uuid) | Q(actor_id=parsed_uuid)
        queryset = queryset.filter(scoped_filter)

    ordering = params.get("ordering")
    if ordering in ORDERING_FIELDS:
        if ordering.lstrip("-") == "created_at":
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by(ordering, "-created_at")

    return queryset



def audit_summary_for_queryset(queryset):
    today = timezone.localdate()
    summary = queryset.aggregate(
        total=Count("id"),
        today=Count("id", filter=Q(created_at__date=today)),
        with_actor=Count("id", filter=Q(actor__isnull=False)),
        request_tracked=Count("id", filter=~Q(request_id="")),
    )
    summary["entity_types"] = queryset.values("entity_type").distinct().count()
    summary["action_types"] = queryset.values("action").distinct().count()
    summary["latest_event_at"] = queryset.order_by("-created_at").values_list("created_at", flat=True).first()
    return summary
