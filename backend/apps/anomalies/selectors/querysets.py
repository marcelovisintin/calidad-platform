from django.db.models import Prefetch

from django.db import models

from apps.accounts.services.access_policy import has_global_access
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

def build_anomaly_queryset(*, detailed: bool = False):
    queryset = Anomaly.objects.select_related(
        "site",
        "area",
        "imputed_area",
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
            "immediate_action__responsible",
        )
    return queryset



def filter_anomaly_queryset_for_user(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()

    if has_global_access(user):
        return queryset

    return queryset.filter(
        models.Q(reporter=user)
        | models.Q(owner=user)
        | models.Q(created_by=user)
        | models.Q(immediate_action__responsible=user)
        | models.Q(participants__user=user)
        | models.Q(action_plans__owner=user)
        | models.Q(action_plans__items__assigned_to=user)
        | models.Q(primary_treatments__participants__user=user)
        | models.Q(primary_treatments__tasks__responsible=user)
        | models.Q(primary_treatments__effectiveness_responsible=user)
        | models.Q(treatment_links__treatment__participants__user=user)
        | models.Q(treatment_links__treatment__tasks__responsible=user)
        | models.Q(treatment_links__treatment__effectiveness_responsible=user)
    ).distinct()

