from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.accounts.constants import (
    PERMISSION_ASSIGN_ACTION,
    PERMISSION_EXECUTE_ACTION,
    PERMISSION_VERIFY_ACTION_EFFECTIVENESS,
    PERMISSION_VIEW_ACTION_ITEM,
    PERMISSION_VIEW_ACTION_PLAN,
)
from apps.accounts.services.authorization import filter_queryset_by_sector_scope
from apps.actions.models import ActionEvidence, ActionItem, ActionItemHistory, ActionItemStatus, ActionPlan

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
    if user.is_superuser:
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
    if user.is_superuser:
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
    if anomaly_id := params.get("anomaly"):
        queryset = queryset.filter(action_plan__anomaly_id=anomaly_id)
    if assigned_to := params.get("assigned_to"):
        queryset = queryset.filter(assigned_to_id=assigned_to)

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

    return queryset



def my_action_items_queryset(user, *, detailed: bool = False, pending_only: bool = False):
    queryset = filter_action_item_queryset_for_user(build_action_item_queryset(detailed=detailed), user)
    queryset = queryset.filter(assigned_to=user)
    if pending_only:
        queryset = queryset.filter(status__in=OPEN_ACTION_ITEM_STATUSES)
    return queryset
