from __future__ import annotations

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.services.access_policy import can_manage_assigned_process, has_global_access
from apps.actions.models import ActionItem, ActionItemStatus
from apps.anomalies.models import AnomalyImmediateAction, AnomalyStage, AnomalyStatus, STAGE_STATUS_MAP


ALLOWED_STAGE_TRANSITIONS = {
    AnomalyStage.REGISTRATION: {
        AnomalyStage.CONTAINMENT,
        AnomalyStage.INITIAL_VERIFICATION,
        AnomalyStage.CLASSIFICATION,
    },
    AnomalyStage.CONTAINMENT: {
        AnomalyStage.INITIAL_VERIFICATION,
        AnomalyStage.CLASSIFICATION,
    },
    AnomalyStage.INITIAL_VERIFICATION: {
        AnomalyStage.CLASSIFICATION,
        AnomalyStage.CAUSE_ANALYSIS,
    },
    AnomalyStage.CLASSIFICATION: {
        AnomalyStage.TREATMENT_CREATED,
        AnomalyStage.CAUSE_ANALYSIS,
        AnomalyStage.PROPOSALS,
        AnomalyStage.ACTION_PLAN,
    },
    AnomalyStage.TREATMENT_CREATED: {
        AnomalyStage.CAUSE_ANALYSIS,
        AnomalyStage.PROPOSALS,
        AnomalyStage.ACTION_PLAN,
    },
    AnomalyStage.CAUSE_ANALYSIS: {
        AnomalyStage.PROPOSALS,
        AnomalyStage.ACTION_PLAN,
    },
    AnomalyStage.PROPOSALS: {
        AnomalyStage.ACTION_PLAN,
    },
    AnomalyStage.ACTION_PLAN: {
        AnomalyStage.EXECUTION_AND_FOLLOW_UP,
    },
    AnomalyStage.EXECUTION_AND_FOLLOW_UP: {
        AnomalyStage.RESULTS,
        AnomalyStage.EFFECTIVENESS_VERIFICATION,
    },
    AnomalyStage.RESULTS: {
        AnomalyStage.EXECUTION_AND_FOLLOW_UP,
        AnomalyStage.EFFECTIVENESS_VERIFICATION,
    },
    AnomalyStage.EFFECTIVENESS_VERIFICATION: {
        AnomalyStage.CLOSURE,
        AnomalyStage.EXECUTION_AND_FOLLOW_UP,
    },
    AnomalyStage.CLOSURE: {
        AnomalyStage.STANDARDIZATION_AND_LEARNING,
    },
    AnomalyStage.STANDARDIZATION_AND_LEARNING: set(),
}

REOPENABLE_STAGES = {
    AnomalyStage.TREATMENT_CREATED,
    AnomalyStage.CAUSE_ANALYSIS,
    AnomalyStage.PROPOSALS,
    AnomalyStage.ACTION_PLAN,
    AnomalyStage.EXECUTION_AND_FOLLOW_UP,
    AnomalyStage.RESULTS,
}



def resolve_status_for_stage(stage: str, *, reopened: bool = False) -> str:
    if reopened:
        return AnomalyStatus.REOPENED
    return STAGE_STATUS_MAP[stage]



def ensure_transition_permission(*, anomaly, user, target_status: str, target_stage: str) -> None:
    if target_status in {AnomalyStatus.CANCELLED, AnomalyStatus.REOPENED}:
        if not has_global_access(user):
            raise PermissionDenied("Solo usuarios ADMIN pueden anular o reabrir anomalias.")
        return

    if target_stage in {AnomalyStage.INITIAL_VERIFICATION, AnomalyStage.CLASSIFICATION}:
        if not has_global_access(user):
            raise PermissionDenied("Solo usuarios ADMIN pueden realizar Revision de hallazgos.")
        return

    if target_stage == AnomalyStage.EFFECTIVENESS_VERIFICATION:
        user_id = getattr(user, "id", None)
        is_assigned = bool(
            user_id
            and (
                anomaly.primary_treatments.filter(effectiveness_responsible_id=user_id).exists()
                or anomaly.treatment_links.filter(treatment__effectiveness_responsible_id=user_id).exists()
                or AnomalyImmediateAction.objects.filter(anomaly=anomaly, responsible_id=user_id).exists()
            )
        )
        if not is_assigned:
            raise PermissionDenied("Solo el usuario asignado puede avanzar la verificacion de eficacia.")
        return

    if not can_manage_assigned_process(user, anomaly.owner_id):
        raise PermissionDenied("Solo el responsable asignado o usuarios ADMIN pueden avanzar esta anomalia.")



def validate_transition(*, anomaly, target_stage: str, target_status: str, comment: str) -> None:
    if not comment or not comment.strip():
        raise ValidationError({"comment": "El comentario de transicion es obligatorio."})

    current_status = anomaly.current_status
    current_stage = anomaly.current_stage

    if current_status == AnomalyStatus.CANCELLED:
        raise ValidationError({"status": "Una anomalia anulada no admite nuevas transiciones."})

    if current_stage == target_stage and current_status == target_status:
        raise ValidationError({"target_stage": "La anomalia ya se encuentra en la etapa indicada."})

    if target_status == AnomalyStatus.CANCELLED:
        if current_status == AnomalyStatus.CLOSED:
            raise ValidationError({"target_status": "No se puede anular una anomalia ya cerrada."})
        return

    if target_status == AnomalyStatus.REOPENED:
        if current_status not in {AnomalyStatus.CLOSED, AnomalyStatus.PENDING_VERIFICATION}:
            raise ValidationError({"target_status": "Solo se puede reabrir desde cierre o verificacion pendiente."})
        if target_stage not in REOPENABLE_STAGES:
            raise ValidationError({"target_stage": "La reapertura debe volver a analisis o tratamiento."})
        return

    if current_status == AnomalyStatus.CLOSED and target_stage != AnomalyStage.STANDARDIZATION_AND_LEARNING:
        raise ValidationError({"target_stage": "Una anomalia cerrada solo puede estandarizarse o reabrirse."})

    allowed_next = ALLOWED_STAGE_TRANSITIONS.get(current_stage, set())
    if target_stage not in allowed_next:
        raise ValidationError({"target_stage": "La transicion solicitada no es valida desde la etapa actual."})

    expected_status = STAGE_STATUS_MAP[target_stage]
    if target_status != expected_status:
        raise ValidationError({"target_status": "El estado destino no coincide con la etapa solicitada."})

    if target_stage == AnomalyStage.ACTION_PLAN and not anomaly.proposals.exists():
        raise ValidationError({"target_stage": "Debe registrar al menos una propuesta antes de definir el plan de accion."})

    if target_stage == AnomalyStage.EXECUTION_AND_FOLLOW_UP and not anomaly.action_plans.exists():
        raise ValidationError({"target_stage": "Debe existir al menos un plan de accion antes de iniciar la ejecucion."})

    if target_stage == AnomalyStage.EFFECTIVENESS_VERIFICATION and not anomaly.result_summary.strip():
        raise ValidationError({"target_stage": "Debe registrar resultados antes de pasar a verificacion de eficacia."})

    if target_stage == AnomalyStage.CLOSURE:
        validate_closure_requirements(anomaly)

    if target_stage == AnomalyStage.STANDARDIZATION_AND_LEARNING and not hasattr(anomaly, "learning"):
        raise ValidationError(
            {"target_stage": "Debe registrar estandarizacion y aprendizaje antes de completar esta etapa."}
        )



def validate_closure_requirements(anomaly) -> None:
    missing_items = []

    if not hasattr(anomaly, "initial_verification"):
        missing_items.append("verificacion inicial")
    if not hasattr(anomaly, "classification"):
        missing_items.append("Revisión de hallazgos")
    if not hasattr(anomaly, "cause_analysis"):
        missing_items.append("analisis de causa")
    if not anomaly.effectiveness_checks.filter(is_effective=True).exists():
        missing_items.append("verificacion de eficacia aprobada")
    if not anomaly.resolution_summary.strip():
        missing_items.append("resolucion")

    open_mandatory_actions = ActionItem.objects.filter(
        action_plan__anomaly=anomaly,
        is_mandatory=True,
    ).exclude(status__in=[ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED])
    if open_mandatory_actions.exists():
        missing_items.append("acciones obligatorias completadas")

    if missing_items:
        raise ValidationError(
            {
                "closure": "No es posible cerrar la anomalia. Faltan: " + ", ".join(missing_items) + "."
            }
        )
