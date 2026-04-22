from datetime import date
from uuid import UUID

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.accounts.constants import (
    PERMISSION_ASSIGN_ACTION,
    PERMISSION_EXECUTE_ACTION,
    PERMISSION_VERIFY_ACTION_EFFECTIVENESS,
    PERMISSION_VIEW_ACTION_ITEM,
    PERMISSION_VIEW_ACTION_PLAN,
    ROLE_ADMINISTRADOR,
)
from apps.accounts.services.authorization import filter_queryset_by_sector_scope
from apps.actions.models import (
    ActionEvidence,
    ActionItem,
    ActionItemHistory,
    ActionItemStatus,
    ActionPlan,
    Treatment,
    TreatmentAnomaly,
)

VISIBLE_ACTION_PERMISSIONS = {
    PERMISSION_VIEW_ACTION_PLAN,
    PERMISSION_VIEW_ACTION_ITEM,
    PERMISSION_ASSIGN_ACTION,
    PERMISSION_EXECUTE_ACTION,
    PERMISSION_VERIFY_ACTION_EFFECTIVENESS,
}

OPEN_ACTION_ITEM_STATUSES = {ActionItemStatus.PENDING, ActionItemStatus.IN_PROGRESS}



def _overdue_filter() -> Q:
    return Q(status__in=OPEN_ACTION_ITEM_STATUSES, due_date__lt=timezone.localdate())



def _has_unrestricted_action_visibility(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    access_level = (getattr(user, "access_level", "") or "").lower()
    if access_level in {"administrador", "desarrollador"}:
        return True

    return user.role_scopes.filter(role__code=ROLE_ADMINISTRADOR).exists()



def build_action_plan_queryset(*, detailed: bool = False):
    queryset = ActionPlan.objects.select_related(
        "anomaly",
        "anomaly__site",
        "anomaly__area",
        "owner",
    )
    if detailed:
        item_queryset = (
            ActionItem.objects.select_related(
                "assigned_to",
                "action_type",
                "priority",
            )
            .prefetch_related(
                Prefetch(
                    "evidences",
                    queryset=ActionEvidence.objects.order_by("-created_at"),
                ),
                Prefetch(
                    "history",
                    queryset=ActionItemHistory.objects.select_related("changed_by").order_by("-changed_at", "-created_at"),
                ),
            )
            .order_by("sequence", "created_at")
        )
        queryset = queryset.prefetch_related(Prefetch("items", queryset=item_queryset))
    return queryset



def build_action_item_queryset(*, detailed: bool = False):
    queryset = ActionItem.objects.select_related(
        "action_plan",
        "action_plan__owner",
        "action_plan__anomaly",
        "action_plan__anomaly__site",
        "action_plan__anomaly__area",
        "action_type",
        "priority",
        "assigned_to",
    ).prefetch_related(
        Prefetch(
            "action_plan__anomaly__primary_treatments",
            queryset=Treatment.objects.only("id", "code", "status", "primary_anomaly_id"),
        ),
        Prefetch(
            "action_plan__anomaly__treatment_links",
            queryset=TreatmentAnomaly.objects.select_related("treatment").only(
                "id",
                "anomaly_id",
                "treatment__id",
                "treatment__code",
                "treatment__status",
            ),
        ),
    )
    if detailed:
        queryset = queryset.prefetch_related(
            Prefetch(
                "evidences",
                queryset=ActionEvidence.objects.order_by("-created_at"),
            ),
            Prefetch(
                "history",
                queryset=ActionItemHistory.objects.select_related("changed_by").order_by("-changed_at", "-created_at"),
            ),
        )
    return queryset



def filter_action_plan_queryset_for_user(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()
    if _has_unrestricted_action_visibility(user):
        return queryset
    if not any(user.has_perm(permission) for permission in VISIBLE_ACTION_PERMISSIONS):
        return queryset.none()
    return filter_queryset_by_sector_scope(
        queryset,
        user,
        area_field="anomaly__area_id",
        site_field="anomaly__site_id",
    )



def filter_action_item_queryset_for_user(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()
    if _has_unrestricted_action_visibility(user):
        return queryset

    assigned_queryset = queryset.filter(assigned_to=user)
    if not any(user.has_perm(permission) for permission in VISIBLE_ACTION_PERMISSIONS):
        return assigned_queryset

    scoped_queryset = filter_queryset_by_sector_scope(
        queryset,
        user,
        area_field="action_plan__anomaly__area_id",
        site_field="action_plan__anomaly__site_id",
    )
    return (scoped_queryset | assigned_queryset).distinct()



def apply_action_item_filters(queryset, params):
    if action_plan_id := params.get("action_plan"):
        queryset = queryset.filter(action_plan_id=action_plan_id)

    if anomaly_value := (params.get("anomaly") or "").strip():
        try:
            anomaly_uuid = UUID(anomaly_value)
            queryset = queryset.filter(action_plan__anomaly_id=anomaly_uuid)
        except ValueError:
            queryset = queryset.filter(
                Q(action_plan__anomaly__code__icontains=anomaly_value)
                | Q(action_plan__anomaly__title__icontains=anomaly_value)
            )

    if treatment_value := (params.get("treatment") or "").strip():
        treatment_filter = Q()
        try:
            treatment_uuid = UUID(treatment_value)
            treatment_filter |= Q(action_plan__anomaly__primary_treatments__id=treatment_uuid)
            treatment_filter |= Q(action_plan__anomaly__treatment_links__treatment_id=treatment_uuid)
        except ValueError:
            treatment_filter |= Q(action_plan__anomaly__primary_treatments__code__icontains=treatment_value)
            treatment_filter |= Q(action_plan__anomaly__treatment_links__treatment__code__icontains=treatment_value)
        queryset = queryset.filter(treatment_filter)

    if assigned_to := params.get("assigned_to"):
        queryset = queryset.filter(assigned_to_id=assigned_to)

    if performed_by := params.get("performed_by"):
        queryset = queryset.filter(
            Q(history__to_status=ActionItemStatus.COMPLETED, history__changed_by_id=performed_by)
            | Q(assigned_to_id=performed_by)
        )

    if completed_on_value := (params.get("completed_on") or "").strip():
        try:
            completed_on = date.fromisoformat(completed_on_value)
            queryset = queryset.filter(completed_at__date=completed_on)
        except ValueError:
            pass

    if query_text := (params.get("q") or "").strip():
        queryset = queryset.filter(
            Q(code__icontains=query_text)
            | Q(title__icontains=query_text)
            | Q(description__icontains=query_text)
            | Q(action_plan__anomaly__code__icontains=query_text)
            | Q(action_plan__anomaly__title__icontains=query_text)
            | Q(assigned_to__username__icontains=query_text)
            | Q(assigned_to__first_name__icontains=query_text)
            | Q(assigned_to__last_name__icontains=query_text)
            | Q(action_plan__anomaly__primary_treatments__code__icontains=query_text)
            | Q(action_plan__anomaly__treatment_links__treatment__code__icontains=query_text)
        )

    status_value = (params.get("status") or "").strip()
    if status_value == "overdue":
        queryset = queryset.filter(_overdue_filter())
    elif status_value:
        queryset = queryset.filter(status=status_value)

    overdue_value = (params.get("overdue") or "").strip().lower()
    if overdue_value in {"1", "true", "yes", "si"}:
        queryset = queryset.filter(_overdue_filter())
    elif overdue_value in {"0", "false", "no"}:
        queryset = queryset.exclude(_overdue_filter())

    return queryset.distinct()



def my_action_items_queryset(user, *, detailed: bool = False, pending_only: bool = False):
    queryset = filter_action_item_queryset_for_user(build_action_item_queryset(detailed=detailed), user)
    queryset = queryset.filter(assigned_to=user)
    if pending_only:
        queryset = queryset.filter(status__in=OPEN_ACTION_ITEM_STATUSES)
    return queryset

