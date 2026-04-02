from __future__ import annotations

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import (
    PERMISSION_ANALYZE_ANOMALY,
    PERMISSION_ASSIGN_ACTION,
    PERMISSION_CANCEL_ANOMALY,
    PERMISSION_CLASSIFY_ANOMALY,
    PERMISSION_CLOSE_ANOMALY,
    PERMISSION_EDIT_ANOMALY,
    PERMISSION_EXECUTE_ACTION,
    PERMISSION_REOPEN_ANOMALY,
    PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
)
from apps.actions.models import ActionItem, ActionItemStatus
from apps.anomalies.models import AnomalyStage, AnomalyStatus, STAGE_STATUS_MAP


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
    AnomalyStage.CAUSE_ANALYSIS,
    AnomalyStage.PROPOSALS,
    AnomalyStage.ACTION_PLAN,
    AnomalyStage.EXECUTION_AND_FOLLOW_UP,
    AnomalyStage.RESULTS,
}



def _require_any_permission(user, permissions: set[str], message: str) -> None:
    if user.is_superuser:
        return
    if any(user.has_perm(permission) for permission in permissions):
        return
    raise PermissionDenied(message)



def resolve_status_for_stage(stage: str, *, reopened: bool = False) -> str:
    if reopened:
        return AnomalyStatus.REOPENED
    return STAGE_STATUS_MAP[stage]



def ensure_transition_permission(*, user, target_status: str, target_stage: str) -> None:
    if target_status == AnomalyStatus.CANCELLED:
        _require_any_permission(user, {PERMISSION_CANCEL_ANOMALY}, "No tiene permisos para anular la anomalia.")
        return

    if target_status == AnomalyStatus.REOPENED:
        _require_any_permission(user, {PERMISSION_REOPEN_ANOMALY}, "No tiene permisos para reabrir la anomalia.")
        return

    if target_stage in {AnomalyStage.INITIAL_VERIFICATION, AnomalyStage.CLASSIFICATION}:
        _require_any_permission(user, {PERMISSION_CLASSIFY_ANOMALY}, "No tiene permisos para clasificar la anomalia.")
        return

    if target_stage in {AnomalyStage.CAUSE_ANALYSIS, AnomalyStage.PROPOSALS}:
        _require_any_permission(user, {PERMISSION_ANALYZE_ANOMALY}, "No tiene permisos para analizar la anomalia.")
        return

    if target_stage == AnomalyStage.ACTION_PLAN:
        _require_any_permission(user, {PERMISSION_ASSIGN_ACTION}, "No tiene permisos para definir el plan de accion.")
        return

    if target_stage in {AnomalyStage.EXECUTION_AND_FOLLOW_UP, AnomalyStage.RESULTS}:
        _require_any_permission(
            user,
            {PERMISSION_EXECUTE_ACTION, PERMISSION_ASSIGN_ACTION, PERMISSION_EDIT_ANOMALY},
            "No tiene permisos para mover la anomalia a tratamiento o seguimiento.",
        )
        return

    if target_stage == AnomalyStage.EFFECTIVENESS_VERIFICATION:
        _require_any_permission(
            user,
            {PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY},
            "No tiene permisos para verificar eficacia.",
        )
        return

    if target_stage in {AnomalyStage.CLOSURE, AnomalyStage.STANDARDIZATION_AND_LEARNING} or target_status == AnomalyStatus.CLOSED:
        _require_any_permission(user, {PERMISSION_CLOSE_ANOMALY}, "No tiene permisos para cerrar la anomalia.")
        return

    _require_any_permission(user, {PERMISSION_EDIT_ANOMALY}, "No tiene permisos para mover la anomalia.")



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
        missing_items.append("clasificacion")
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
