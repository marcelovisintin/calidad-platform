"""One observation manages several findings without duplicating its actions."""

from datetime import date

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.anomalies.models import (
    Anomaly, AnomalyClassification, AnomalyImmediateAction, AnomalyInitialVerification, AnomalyStage,
    AnomalyStatus, ObservationResolutionPath, ParticipantRole,
)
from apps.anomalies.services.classification_rules import immediate_action_q, is_nonconformity_anomaly
from apps.audit.services import record_audit_event
from apps.notifications.services.notification_service import (
    create_internal_notification, sync_finding_management_task_status,
)


def open_observation_options() -> QuerySet[Anomaly]:
    return (
        Anomaly.objects.filter(
            immediate_action_q(), observation_parent__isnull=True,
            observation_resolution_path=ObservationResolutionPath.OBSERVATION,
            immediate_action__responsible__is_active=True,
            current_status__in=[AnomalyStatus.IN_EVALUATION, AnomalyStatus.IN_TREATMENT],
        )
        .filter(
            Q(severity__code__iexact="OBS") | Q(severity__code__icontains="observaci")
            | Q(severity__name__icontains="observaci") | Q(severity__name__icontains="inmediata")
        )
        .filter(immediate_action__action_completed_at__isnull=True)
        .filter(Q(observation_actions__status="pending") | Q(observation_actions__isnull=True))
        .exclude(immediate_action__effectiveness_is_effective=True)
        .exclude(treatment_links__isnull=False)
        .distinct()
    )


@transaction.atomic
def associate_to_observation(
    *, anomaly: Anomaly, observation: Anomaly, user: User, reason: str, request_id: str = "",
) -> Anomaly:
    from .anomaly_service import (
        _require_admin_access_level, _ensure_anomaly_is_editable, _ensure_observation_code,
        _ensure_participant_role, _write_status_history, snapshot_anomaly,
    )
    _require_admin_access_level(user, "Solo ADMIN puede asociar anomalias a observaciones.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Debe fundamentar por que las acciones cubren esta anomalia."})
    _ensure_anomaly_is_editable(anomaly)
    # Both locks use the same order for competing associations.
    locked = {item.pk: item for item in Anomaly.objects.select_for_update().filter(
        pk__in=[anomaly.pk, observation.pk],
    ).order_by("pk")}
    source, target = locked[anomaly.pk], locked[observation.pk]
    _ensure_anomaly_is_editable(source)
    if source.pk == target.pk or not open_observation_options().filter(pk=target.pk).exists():
        raise ValidationError({"observation": "Seleccione una observacion abierta con gestion o acciones pendientes."})
    if source.current_status in {AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED}:
        raise ValidationError({"anomaly": "La anomalia esta cerrada o anulada."})
    if is_nonconformity_anomaly(source):
        raise ValidationError({"anomaly": "Revise y justifique la clasificacion NC antes de asociar a una Observacion."})
    if (source.observation_parent_id or source.associated_observation_anomalies.exists()
            or source.treatment_links.exists() or source.observation_actions.exists()
            or source.action_plans.exists() or source.effectiveness_checks.exists()
            or source.current_stage not in {
                AnomalyStage.REGISTRATION, AnomalyStage.CONTAINMENT,
                AnomalyStage.INITIAL_VERIFICATION, AnomalyStage.CLASSIFICATION,
            }):
        raise ValidationError({"anomaly": "La anomalia ya tiene una gestion asociada o iniciada."})
    existing = getattr(source, "immediate_action", None)
    if existing and (existing.observation.strip() or existing.actions_taken.strip() or existing.effectiveness_verified_at):
        raise ValidationError({"anomaly": "La Observacion ya tiene gestion propia; no puede fusionarse."})
    before = snapshot_anomaly(source)
    previous_status, previous_stage = source.current_status, source.current_stage
    old_deadline = source.deadline
    source.observation_parent = target
    source.severity = target.severity
    source.owner = target.immediate_action.responsible
    source.classification_change_unlocked = False
    source.observation_resolution_path = ObservationResolutionPath.OBSERVATION
    source.classification_summary = f"Observacion compartida: {target.code}. Motivo: {reason}"
    source.current_status, source.current_stage = target.current_status, target.current_stage
    source.last_transition_at = timezone.now()
    source.updated_by = user
    source.row_version += 1
    _ensure_observation_code(source)
    source.full_clean()
    source.save()
    AnomalyClassification.objects.update_or_create(
        anomaly=source,
        defaults=dict(classified_by=user, classified_at=timezone.now(),
                      requires_action_plan=True, requires_effectiveness_verification=True,
                      summary=source.classification_summary, updated_by=user),
    )
    AnomalyInitialVerification.objects.get_or_create(
        anomaly=source, defaults={
            "verified_by": user, "verified_at": timezone.now(),
            "summary": f"Revision de hallazgos confirmada al asociar a {target.code}. Motivo: {reason}",
            "created_by": user, "updated_by": user,
        },
    )
    # An unused placeholder from an earlier classification is replaced by the link.
    if existing:
        existing.delete()
    _ensure_participant_role(anomaly=source, participant_user=source.owner,
                             role=ParticipantRole.OWNER, actor=user, note="Responsable de Observacion compartida.")
    sync_finding_management_task_status(anomaly=source, task_status="dismissed", actor=user, request_id=request_id)
    evidence = (f"Motivo: {reason}\nResponsable: {source.owner.full_name}\n"
                f"Fecha limite anterior: {old_deadline or 'Sin fecha'}\n"
                f"Fecha limite compartida: {target.deadline or 'Sin fecha'}")
    _write_status_history(anomaly=source, from_status=previous_status, to_status=source.current_status,
                          from_stage=previous_stage, to_stage=source.current_stage,
                          comment=f"Anomalia clasificada como Observacion y asociada a {target.code}.",
                          evidence_note=evidence, actor=user, changed_at=source.last_transition_at)
    _write_status_history(anomaly=target, from_status=target.current_status, to_status=target.current_status,
                          from_stage=target.current_stage, to_stage=target.current_stage,
                          comment=f"Se incorpora la anomalia {source.code} a esta Observacion.",
                          evidence_note=evidence, actor=user, changed_at=source.last_transition_at)
    record_audit_event(entity=source, action="observation.anomaly_associated", actor=user,
                       before_data=before, after_data={**snapshot_anomaly(source),
                       "observation_id": str(target.pk), "reason": reason}, request_id=request_id)
    create_internal_notification(
        recipients=[source.owner], title=f"Anomalia {source.code} asociada a la Observacion {target.code}",
        body=f"Las acciones de la Observacion {target.code} deben cubrir tambien {source.code}.\nMotivo: {reason}",
        source_type="anomalies.anomaly", source_id=target.pk, actor=user,
        template_code="observation_anomaly_associated", action_url=f"/anomalies/observations?anomaly={target.pk}",
        context_data={"anomaly_id": str(source.pk), "observation_id": str(target.pk)},
        email_enabled=True, email_template_code="observation_anomaly_associated",
        email_context={"recipient_name": source.owner.full_name, "anomaly_code": source.code,
                       "observation_code": target.code, "reason": reason}, request_id=request_id,
    )
    return source


def sync_observation_anomalies(
    *, observation: Anomaly, user: User, comment: str, request_id: str = "",
) -> None:
    from .anomaly_service import _write_status_history, snapshot_anomaly
    from apps.notifications.services import notify_anomaly_closed

    for source in observation.associated_observation_anomalies.select_for_update().order_by("pk"):
        before = snapshot_anomaly(source)
        previous_status, previous_stage, previous_closed = source.current_status, source.current_stage, source.closed_at
        for field in ("owner_id", "current_status", "current_stage", "closed_at", "last_transition_at",
                      "result_summary", "effectiveness_summary", "closure_comment"):
            setattr(source, field, getattr(observation, field))
        source.updated_by = user
        source.row_version += 1
        source.save()
        _write_status_history(
            anomaly=source, from_status=previous_status, to_status=source.current_status,
            from_stage=previous_stage, to_stage=source.current_stage,
            comment=f"Observacion compartida {observation.code}: {comment}",
            evidence_note=observation.effectiveness_summary or observation.resolution_summary,
            actor=user, changed_at=timezone.now(),
        )
        record_audit_event(entity=source, action="observation.shared_progress", actor=user,
                           before_data=before, after_data=snapshot_anomaly(source), request_id=request_id)
        if source.closed_at and not previous_closed:
            notify_anomaly_closed(anomaly=source, actor=user, closure_path="observation_effective", request_id=request_id)


@transaction.atomic
def detach_from_observation(
    *, anomaly: Anomaly, user: User, reason: str, observation_due_date: date, request_id: str = "",
) -> Anomaly:
    from .anomaly_service import _require_admin_access_level, _write_status_history, snapshot_anomaly
    from apps.notifications.services import notify_finding_management_assigned

    _require_admin_access_level(user, "Solo ADMIN puede separar una anomalia de una Observacion.")
    if not reason.strip():
        raise ValidationError({"reason": "Debe indicar el motivo de separacion."})
    if not anomaly.observation_parent_id:
        raise ValidationError({"anomaly": "La anomalia no tiene una Observacion asociada."})
    # Progress updates lock the primary observation before its linked findings.
    parent = Anomaly.objects.select_for_update().get(pk=anomaly.observation_parent_id)
    source = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    if source.observation_parent_id != parent.pk or source.current_status in {AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED}:
        raise ValidationError({"anomaly": "Solo se pueden separar anomalias asociadas cuya gestion sigue abierta."})
    before = snapshot_anomaly(source)
    previous_status, previous_stage = source.current_status, source.current_stage
    previous_deadline = source.deadline
    source.observation_parent = None
    source.current_status = AnomalyStatus.IN_EVALUATION
    source.current_stage = AnomalyStage.CLASSIFICATION
    source.last_transition_at = timezone.now()
    source.result_summary = source.effectiveness_summary = source.closure_comment = ""
    source.classification_summary = f"Observacion independiente tras separacion de {parent.code}. Motivo: {reason.strip()}"
    source.updated_by = user
    source.row_version += 1
    source.save()
    AnomalyClassification.objects.filter(anomaly=source).update(summary=source.classification_summary)
    AnomalyImmediateAction.objects.create(anomaly=source, responsible=source.owner,
                                         action_date=observation_due_date, observation="",
                                         created_by=user, updated_by=user)
    evidence = (f"Motivo: {reason.strip()}\nObservacion anterior: {parent.code}\n"
                f"Fecha limite anterior: {previous_deadline or 'Sin fecha'}\n"
                f"Nueva fecha limite: {observation_due_date.isoformat()}")
    for item in (source, parent):
        _write_status_history(
            anomaly=item, from_status=previous_status if item.pk == source.pk else item.current_status,
            to_status=item.current_status, from_stage=previous_stage if item.pk == source.pk else item.current_stage,
            to_stage=item.current_stage, comment=f"ADMIN separa {source.code} de la Observacion {parent.code}.",
            evidence_note=evidence, actor=user, changed_at=source.last_transition_at,
        )
    record_audit_event(entity=source, action="observation.anomaly_detached", actor=user,
                       before_data=before, after_data={**snapshot_anomaly(source), "reason": reason.strip()},
                       request_id=request_id)
    notify_finding_management_assigned(anomaly=source, responsible=source.owner, actor=user, request_id=request_id)
    return source
