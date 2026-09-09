from django.db.models import Prefetch, Q
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.accounts.services.access_policy import has_global_access
from apps.actions.api.validation_item_serializers import ValidationItemSerializer
from apps.actions.models import Treatment, TreatmentTask
from apps.actions.services.treatment_service import (
    can_validate_treatment_effectiveness,
    get_treatment_validation_state,
)
from apps.anomalies.models import (
    Anomaly,
    AnomalyStatus,
    ObservationAction,
    ObservationResolutionPath,
)
from common.pagination import DefaultPageNumberPagination
from common.permissions import IsAuthenticatedAndActive
from common.deadlines import is_overdue


VALIDATION_ITEM_SOURCES = {"treatment", "observation"}


def _parse_sources(params) -> set[str]:
    if "source" not in params:
        return set(VALIDATION_ITEM_SOURCES)

    sources = {
        source.strip().lower()
        for raw_value in params.getlist("source")
        for source in raw_value.split(",")
        if source.strip()
    }
    invalid_sources = sources - VALIDATION_ITEM_SOURCES
    if invalid_sources:
        raise ValidationError(
            {"source": "Los origenes permitidos son treatment y observation."}
        )
    return sources


def _treatment_validation_queryset(user, query_text: str):
    queryset = (
        Treatment.objects.filter(effectiveness_responsible__isnull=False)
        .select_related("primary_anomaly", "effectiveness_responsible")
        .prefetch_related(
            "root_causes",
            Prefetch("tasks", queryset=TreatmentTask.objects.order_by("created_at")),
        )
    )
    if not has_global_access(user):
        queryset = queryset.filter(effectiveness_responsible=user)
    if query_text:
        queryset = queryset.filter(
            Q(code__icontains=query_text)
            | Q(primary_anomaly__code__icontains=query_text)
            | Q(primary_anomaly__title__icontains=query_text)
            | Q(effectiveness_responsible__username__icontains=query_text)
            | Q(effectiveness_responsible__first_name__icontains=query_text)
            | Q(effectiveness_responsible__last_name__icontains=query_text)
        )
    return queryset.distinct()


def _observation_validation_queryset(user, query_text: str):
    queryset = (
        Anomaly.objects.filter(
            observation_resolution_path=ObservationResolutionPath.OBSERVATION,
            immediate_action__isnull=False,
        )
        .filter(
            Q(observation_actions__isnull=False)
            | (Q(immediate_action__actions_taken__isnull=False) & ~Q(immediate_action__actions_taken=""))
        )
        .select_related("immediate_action", "immediate_action__responsible")
        .prefetch_related(
            Prefetch(
                "observation_actions",
                queryset=ObservationAction.objects.order_by("sequence", "created_at"),
            )
        )
    )
    if not has_global_access(user):
        queryset = queryset.filter(immediate_action__responsible=user)
    if query_text:
        queryset = queryset.filter(
            Q(code__icontains=query_text)
            | Q(title__icontains=query_text)
            | Q(immediate_action__observation__icontains=query_text)
            | Q(immediate_action__responsible__username__icontains=query_text)
            | Q(immediate_action__responsible__first_name__icontains=query_text)
            | Q(immediate_action__responsible__last_name__icontains=query_text)
        )
    return queryset.distinct()


def _treatment_validation_item(treatment, user) -> dict:
    validation_state = get_treatment_validation_state(treatment)
    result = treatment.effectiveness_validation_result or ""
    is_completed = result == "effective"
    status = "completed" if is_completed else ("pending" if validation_state["available"] else "blocked")
    return {
        "id": treatment.pk,
        "source": "treatment",
        "is_overdue": treatment.effectiveness_is_overdue,
        "code": treatment.code,
        "title": treatment.primary_anomaly.title,
        "status": status,
        "due_date": treatment.effectiveness_evaluation_date,
        "responsible": treatment.effectiveness_responsible,
        "result": result,
        "validated_at": treatment.effectiveness_validated_at,
        "validation_comment": treatment.effectiveness_validation_comment or "",
        "available": validation_state["available"] and not is_completed,
        "blockers": validation_state["blockers"],
        "can_validate": (
            not is_completed
            and validation_state["available"]
            and can_validate_treatment_effectiveness(user, treatment)
        ),
        "created_at": treatment.created_at,
        "updated_at": treatment.updated_at,
    }


def _observation_validation_item(anomaly, user) -> dict:
    observation = anomaly.immediate_action
    actions = list(anomaly.observation_actions.all())
    reference_action = max(
        actions,
        key=lambda action: (action.effectiveness_due_date, action.sequence),
        default=None,
    )
    has_action = bool(actions or (observation.actions_taken or "").strip())
    result = (
        "effective"
        if observation.effectiveness_is_effective is True
        else "not_effective"
        if observation.effectiveness_is_effective is False
        else ""
    )
    blockers = [] if has_action else ["Debe cargar al menos una accion antes de verificar eficacia."]
    if anomaly.current_status == AnomalyStatus.CANCELLED:
        blockers.append("La Observacion esta anulada.")
    available = not blockers and not result
    return {
        "id": anomaly.pk,
        "source": "observation",
        "is_overdue": is_overdue(
            reference_action.effectiveness_due_date if reference_action else observation.effectiveness_due_at,
            anomaly.current_status,
            finished=bool(observation.effectiveness_verified_at),
        ),
        "code": anomaly.code,
        "title": anomaly.title,
        "status": "completed" if result else ("pending" if available else "blocked"),
        "due_date": (
            reference_action.effectiveness_due_date
            if reference_action
            else observation.effectiveness_due_at
        ),
        "responsible": observation.responsible,
        "result": result,
        "validated_at": observation.effectiveness_verified_at,
        "validation_comment": observation.effectiveness_comment or "",
        "available": available,
        "blockers": blockers,
        "can_validate": available and observation.responsible_id == getattr(user, "id", None),
        "created_at": anomaly.created_at,
        "updated_at": anomaly.updated_at,
    }


class ValidationItemListAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    pagination_class = DefaultPageNumberPagination

    def get(self, request):
        sources = _parse_sources(request.query_params)
        query_text = (request.query_params.get("q") or "").strip()
        items = []

        if "treatment" in sources:
            items.extend(
                _treatment_validation_item(treatment, request.user)
                for treatment in _treatment_validation_queryset(request.user, query_text)
            )
        if "observation" in sources:
            items.extend(
                _observation_validation_item(anomaly, request.user)
                for anomaly in _observation_validation_queryset(request.user, query_text)
            )

        status_value = (request.query_params.get("status") or "").strip().lower()
        if status_value:
            if status_value not in {"pending", "blocked", "completed"}:
                raise ValidationError(
                    {"status": "Los estados permitidos son pending, blocked y completed."}
                )
            items = [item for item in items if item["status"] == status_value]

        items.sort(key=lambda item: (item["updated_at"], item["created_at"]), reverse=True)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(items, request, view=self)
        serializer = ValidationItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
