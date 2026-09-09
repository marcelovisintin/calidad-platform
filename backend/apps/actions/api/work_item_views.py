from uuid import UUID

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.accounts.services.access_policy import (
    can_execute_assignment,
    can_manage_assigned_process,
    has_global_access,
)
from apps.actions.api.work_item_serializers import ActionWorkItemSerializer
from apps.actions.models import (
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskEvidence,
    TreatmentTaskStatus,
)
from apps.actions.services import can_manage_treatment
from apps.anomalies.models import ObservationAction, ObservationActionStatus
from common.pagination import DefaultPageNumberPagination
from common.permissions import IsAuthenticatedAndActive
from common.query_params import parse_iso_date_parameter


WORK_ITEM_SOURCES = {"treatment", "observation"}


def _parse_sources(params) -> set[str]:
    if "source" not in params:
        return set(WORK_ITEM_SOURCES)

    sources = {
        source.strip().lower()
        for raw_value in params.getlist("source")
        for source in raw_value.split(",")
        if source.strip()
    }
    invalid_sources = sources - WORK_ITEM_SOURCES
    if invalid_sources:
        raise ValidationError(
            {"source": "Los origenes permitidos son treatment y observation."}
        )
    return sources


def _parse_uuid(value: str, *, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Debe indicar un UUID valido."}) from exc


def _anomaly_filter(value: str, *, observation: bool) -> Q:
    try:
        anomaly_id = UUID(value)
    except ValueError:
        if observation:
            return Q(anomaly__code__icontains=value) | Q(anomaly__title__icontains=value)
        return (
            Q(anomaly_links__anomaly__code__icontains=value)
            | Q(anomaly_links__anomaly__title__icontains=value)
            | Q(treatment__primary_anomaly__code__icontains=value)
            | Q(treatment__primary_anomaly__title__icontains=value)
        )

    if observation:
        return Q(anomaly_id=anomaly_id)
    return Q(anomaly_links__anomaly_id=anomaly_id) | Q(treatment__primary_anomaly_id=anomaly_id)


def _treatment_items_queryset(user, params):
    queryset = (
        TreatmentTask.objects.select_related(
            "responsible",
            "treatment",
            "treatment__primary_anomaly",
        )
        .prefetch_related(
            "root_causes",
            Prefetch(
                "evidences",
                queryset=TreatmentTaskEvidence.objects.select_related("uploaded_by").order_by("-created_at"),
            ),
            Prefetch(
                "anomaly_links",
                queryset=TreatmentTaskAnomaly.objects.select_related("anomaly").order_by("created_at"),
            )
        )
    )
    if not has_global_access(user):
        queryset = queryset.filter(responsible=user)

    if query_text := (params.get("q") or "").strip():
        queryset = queryset.filter(
            Q(code__icontains=query_text)
            | Q(title__icontains=query_text)
            | Q(description__icontains=query_text)
            | Q(treatment__code__icontains=query_text)
            | Q(treatment__primary_anomaly__code__icontains=query_text)
            | Q(treatment__primary_anomaly__title__icontains=query_text)
            | Q(anomaly_links__anomaly__code__icontains=query_text)
            | Q(anomaly_links__anomaly__title__icontains=query_text)
            | Q(responsible__username__icontains=query_text)
            | Q(responsible__first_name__icontains=query_text)
            | Q(responsible__last_name__icontains=query_text)
        )
    if anomaly_value := (params.get("anomaly") or "").strip():
        queryset = queryset.filter(_anomaly_filter(anomaly_value, observation=False))
    if treatment_value := (params.get("treatment") or "").strip():
        try:
            queryset = queryset.filter(treatment_id=UUID(treatment_value))
        except ValueError:
            queryset = queryset.filter(treatment__code__icontains=treatment_value)
    if responsible_value := (params.get("responsible") or "").strip():
        queryset = queryset.filter(
            responsible_id=_parse_uuid(responsible_value, field_name="responsible")
        )

    status_value = (params.get("status") or "").strip().lower()
    if status_value == "overdue":
        queryset = queryset.filter(
            status__in=[TreatmentTaskStatus.PENDING, TreatmentTaskStatus.IN_PROGRESS],
            execution_date__lt=timezone.localdate(),
        ).exclude(treatment__status__in=["completed", "cancelled"])
    elif status_value:
        queryset = queryset.filter(status=status_value)

    if completed_on_value := (params.get("completed_on") or "").strip():
        completed_on = parse_iso_date_parameter(completed_on_value, field_name="completed_on")
        queryset = queryset.filter(completed_at__date=completed_on)

    return queryset.distinct()


def _observation_items_queryset(user, params):
    queryset = ObservationAction.objects.select_related(
        "anomaly",
        "anomaly__immediate_action",
        "anomaly__immediate_action__responsible",
    )
    if not has_global_access(user):
        queryset = queryset.filter(anomaly__immediate_action__responsible=user)

    if query_text := (params.get("q") or "").strip():
        queryset = queryset.filter(
            Q(detail__icontains=query_text)
            | Q(anomaly__code__icontains=query_text)
            | Q(anomaly__title__icontains=query_text)
            | Q(anomaly__immediate_action__responsible__username__icontains=query_text)
            | Q(anomaly__immediate_action__responsible__first_name__icontains=query_text)
            | Q(anomaly__immediate_action__responsible__last_name__icontains=query_text)
        )
    if anomaly_value := (params.get("anomaly") or "").strip():
        queryset = queryset.filter(_anomaly_filter(anomaly_value, observation=True))
    if responsible_value := (params.get("responsible") or "").strip():
        queryset = queryset.filter(
            anomaly__immediate_action__responsible_id=_parse_uuid(
                responsible_value,
                field_name="responsible",
            )
        )

    status_value = (params.get("status") or "").strip().lower()
    if status_value == "overdue":
        queryset = queryset.filter(
            status=ObservationActionStatus.PENDING,
            estimated_completion_date__lt=timezone.localdate(),
        ).exclude(anomaly__current_status__in=["closed", "cancelled"])
    elif status_value:
        queryset = queryset.filter(status=status_value)

    if completed_on_value := (params.get("completed_on") or "").strip():
        completed_on = parse_iso_date_parameter(completed_on_value, field_name="completed_on")
        queryset = queryset.filter(completed_at=completed_on)

    return queryset.distinct()


def _anomaly_summary(anomaly) -> dict:
    return {
        "id": anomaly.pk,
        "code": anomaly.code,
        "title": anomaly.title,
        "current_status": anomaly.current_status,
        "current_stage": anomaly.current_stage,
    }


def _treatment_work_item(task, user) -> dict:
    anomalies = [link.anomaly for link in task.anomaly_links.all()]
    if not anomalies:
        anomalies = [task.treatment.primary_anomaly]

    return {
        "id": task.pk,
        "source": "treatment",
        "code": task.code,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "due_date": task.execution_date,
        "completed_on": task.completed_at.date() if task.completed_at else None,
        "effectiveness_due_date": None,
        "is_overdue": task.is_overdue,
        "responsible": task.responsible,
        "completed_by": task.responsible if task.completed_at else None,
        "treatment": {
            "id": task.treatment.pk,
            "code": task.treatment.code,
            "status": task.treatment.status,
        },
        "anomalies": [_anomaly_summary(anomaly) for anomaly in anomalies],
        "root_causes": list(task.root_causes.all()),
        "evidences": list(task.evidences.all()),
        "can_manage": can_manage_treatment(user, task.treatment),
        "can_update_status": can_execute_assignment(user, task.responsible_id),
        "can_add_evidence": can_execute_assignment(user, task.responsible_id),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _observation_work_item(action, user) -> dict:
    immediate_action = action.anomaly.immediate_action
    responsible = immediate_action.responsible
    can_manage = can_manage_assigned_process(user, immediate_action.responsible_id)
    return {
        "id": action.pk,
        "source": "observation",
        "code": f"{action.anomaly.code}-A{action.sequence:02d}",
        "title": f"Accion {action.sequence} de Observacion",
        "description": action.detail,
        "status": action.status,
        "due_date": action.estimated_completion_date,
        "completed_on": action.completed_at,
        "effectiveness_due_date": action.effectiveness_due_date,
        "is_overdue": action.is_overdue,
        "responsible": responsible,
        "completed_by": action.completed_by,
        "treatment": None,
        "anomalies": [_anomaly_summary(action.anomaly)],
        "root_causes": [],
        "evidences": [],
        "can_manage": can_manage,
        "can_update_status": can_manage,
        "can_add_evidence": False,
        "created_at": action.created_at,
        "updated_at": action.updated_at,
    }


class ActionWorkItemListAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        sources = _parse_sources(request.query_params)
        items = []

        if "treatment" in sources:
            items.extend(
                _treatment_work_item(task, request.user)
                for task in _treatment_items_queryset(request.user, request.query_params)
            )
        if "observation" in sources and not (request.query_params.get("treatment") or "").strip():
            items.extend(
                _observation_work_item(action, request.user)
                for action in _observation_items_queryset(request.user, request.query_params)
            )

        items.sort(key=lambda item: (item["updated_at"], item["created_at"]), reverse=True)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(items, request, view=self)
        serializer = ActionWorkItemSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
