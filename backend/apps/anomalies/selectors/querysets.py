from django.db.models import Prefetch

from apps.accounts.constants import (
    PERMISSION_ANALYZE_ANOMALY,
    PERMISSION_CLASSIFY_ANOMALY,
    PERMISSION_CLOSE_ANOMALY,
    PERMISSION_CREATE_ANOMALY,
    PERMISSION_EDIT_ANOMALY,
    PERMISSION_REOPEN_ANOMALY,
    PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
    PERMISSION_VIEW_ALL_ANOMALY,
    PERMISSION_VIEW_SECTOR_ANOMALY,
)
from apps.accounts.services.authorization import filter_queryset_by_sector_scope
from apps.actions.models import ActionItem, ActionPlan
from apps.anomalies.models import (
    Anomaly,
    AnomalyAttachment,
    AnomalyComment,
    AnomalyEffectivenessCheck,
    AnomalyParticipant,
    AnomalyProposal,
    AnomalyStatusHistory,
)

VISIBLE_ANOMALY_PERMISSIONS = {
    PERMISSION_VIEW_ALL_ANOMALY,
    PERMISSION_VIEW_SECTOR_ANOMALY,
    PERMISSION_CREATE_ANOMALY,
    PERMISSION_EDIT_ANOMALY,
    PERMISSION_CLASSIFY_ANOMALY,
    PERMISSION_ANALYZE_ANOMALY,
    PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
    PERMISSION_CLOSE_ANOMALY,
    PERMISSION_REOPEN_ANOMALY,
}



def build_anomaly_queryset(*, detailed: bool = False):
    queryset = Anomaly.objects.select_related(
        "site",
        "area",
        "line",
        "reporter",
        "owner",
        "anomaly_type",
        "anomaly_origin",
        "severity",
        "priority",
        "duplicate_of",
    )

    if detailed:
        queryset = queryset.prefetch_related(
            Prefetch(
                "comments",
                queryset=AnomalyComment.objects.select_related("author").order_by("created_at"),
            ),
            Prefetch(
                "attachments",
                queryset=AnomalyAttachment.objects.select_related("uploaded_by").order_by("-created_at"),
            ),
            Prefetch(
                "participants",
                queryset=AnomalyParticipant.objects.select_related("user").order_by("role", "user__username"),
            ),
            Prefetch(
                "proposals",
                queryset=AnomalyProposal.objects.select_related("proposed_by").order_by("sequence", "created_at"),
            ),
            Prefetch(
                "effectiveness_checks",
                queryset=AnomalyEffectivenessCheck.objects.select_related("verified_by").order_by("-verified_at", "-created_at"),
            ),
            Prefetch(
                "status_history",
                queryset=AnomalyStatusHistory.objects.select_related("changed_by").order_by("-changed_at", "-created_at"),
            ),
            Prefetch(
                "action_plans",
                queryset=ActionPlan.objects.select_related("owner").prefetch_related(
                    Prefetch(
                        "items",
                        queryset=ActionItem.objects.select_related("assigned_to", "action_type", "priority").order_by("sequence", "created_at"),
                    )
                ).order_by("-created_at"),
            ),
            "initial_verification__verified_by",
            "classification__classified_by",
            "cause_analysis__analyzed_by",
            "learning__recorded_by",
        )
    return queryset



def filter_anomaly_queryset_for_user(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()

    access_level = getattr(user, "access_level", "")
    if user.is_superuser or access_level in {"administrador", "desarrollador"}:
        return queryset

    if not any(user.has_perm(permission) for permission in VISIBLE_ANOMALY_PERMISSIONS):
        return queryset.filter(reporter=user)

    scoped_queryset = filter_queryset_by_sector_scope(queryset, user)
    return (scoped_queryset | queryset.filter(reporter=user)).distinct()

