from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import (
    PERMISSION_ANALYZE_ANOMALY,
    PERMISSION_ASSIGN_ACTION,
    PERMISSION_CLASSIFY_ANOMALY,
    PERMISSION_CLOSE_ANOMALY,
    PERMISSION_CREATE_ANOMALY,
    PERMISSION_EDIT_ANOMALY,
    PERMISSION_EXECUTE_ACTION,
    PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
)
from apps.accounts.services.authorization import can_access_area
from apps.audit.services import record_audit_event
from apps.notifications.services import notify_anomaly_created, notify_participation_request
from apps.anomalies.models import (
    Anomaly,
    AnomalyAttachment,
    AnomalyCauseAnalysis,
    AnomalyClassification,
    AnomalyComment,
    AnomalyEffectivenessCheck,
    AnomalyInitialVerification,
    AnomalyLearning,
    AnomalyParticipant,
    AnomalyProposal,
    AnomalyStage,
    AnomalyStatus,
    AnomalyStatusHistory,
    ParticipantRole,
)
from apps.anomalies.services.workflow import (
    ensure_transition_permission,
    resolve_status_for_stage,
    validate_transition,
)



def _require_permission(user, permission: str, message: str) -> None:
    if user.is_superuser:
        return
    if not user.has_perm(permission):
        raise PermissionDenied(message)



def _require_any_permission(user, permissions: set[str], message: str) -> None:
    if user.is_superuser:
        return
    if any(user.has_perm(permission) for permission in permissions):
        return
    raise PermissionDenied(message)


def _can_create_anomaly(user) -> bool:
    if user.is_superuser:
        return True
    if getattr(user, "access_level", "") == "usuario_activo":
        return True
    return user.has_perm(PERMISSION_CREATE_ANOMALY)



def _ensure_scope(site_id, area_id, user) -> None:
    if user.is_superuser:
        return
    if not can_access_area(user, area_id=area_id, site_id=site_id):
        raise PermissionDenied("No tiene alcance sobre el sitio o sector de la anomalia.")



def _bump_version(instance) -> None:
    instance.row_version = (instance.row_version or 0) + 1



def _request_id(value: str | None) -> str:
    return (value or "").strip()



def _get_related_or_none(instance, attr_name: str):
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return None



def snapshot_anomaly(anomaly: Anomaly) -> dict:
    return {
        "id": str(anomaly.pk),
        "code": anomaly.code,
        "title": anomaly.title,
        "current_status": anomaly.current_status,
        "current_stage": anomaly.current_stage,
        "site_id": str(anomaly.site_id) if anomaly.site_id else "",
        "area_id": str(anomaly.area_id) if anomaly.area_id else "",
        "line_id": str(anomaly.line_id) if anomaly.line_id else "",
        "reporter_id": str(anomaly.reporter_id) if anomaly.reporter_id else "",
        "owner_id": str(anomaly.owner_id) if anomaly.owner_id else "",
        "severity_id": str(anomaly.severity_id) if anomaly.severity_id else "",
        "priority_id": str(anomaly.priority_id) if anomaly.priority_id else "",
        "detected_at": anomaly.detected_at,
        "manufacturing_order_number": anomaly.manufacturing_order_number,
        "affected_quantity": anomaly.affected_quantity,
        "affected_process": anomaly.affected_process,
        "last_transition_at": anomaly.last_transition_at,
        "closed_at": anomaly.closed_at,
    }



def generate_anomaly_code() -> str:
    year = timezone.localdate().year
    prefix = str(year)
    last_code = (
        Anomaly.objects.filter(code__startswith=prefix, code__regex=rf"^{year}\d{{4}}$")
        .order_by("-code")
        .values_list("code", flat=True)
        .first()
    )

    sequence = 1
    if last_code:
        try:
            sequence = int(last_code[4:]) + 1
        except (TypeError, ValueError):
            sequence = (
                Anomaly.objects.filter(code__startswith=prefix, code__regex=rf"^{year}\d{{4}}$")
                .count()
                + 1
            )

    while True:
        candidate = f"{prefix}{sequence:04d}"
        if not Anomaly.objects.filter(code=candidate).exists():
            return candidate
        sequence += 1



def _ensure_default_participants(anomaly: Anomaly, actor) -> None:
    AnomalyParticipant.objects.get_or_create(
        anomaly=anomaly,
        user=anomaly.reporter,
        role=ParticipantRole.REPORTER,
        defaults={"created_by": actor, "updated_by": actor},
    )
    if anomaly.owner_id:
        AnomalyParticipant.objects.get_or_create(
            anomaly=anomaly,
            user=anomaly.owner,
            role=ParticipantRole.OWNER,
            defaults={"created_by": actor, "updated_by": actor},
        )


def _ensure_participant_role(*, anomaly: Anomaly, participant_user, role: str, actor, note: str = "") -> None:
    participant, created = AnomalyParticipant.objects.get_or_create(
        anomaly=anomaly,
        user=participant_user,
        role=role,
        defaults={"note": note, "created_by": actor, "updated_by": actor},
    )
    if created:
        return

    changed = False
    if note and participant.note != note:
        participant.note = note
        changed = True
    if participant.updated_by_id != actor.id:
        participant.updated_by = actor
        changed = True
    if changed:
        participant.full_clean()
        participant.save()

def _write_status_history(*, anomaly: Anomaly, from_status: str, to_status: str, from_stage: str, to_stage: str, comment: str, actor, changed_at):
    return AnomalyStatusHistory.objects.create(
        anomaly=anomaly,
        from_status=from_status,
        to_status=to_status,
        from_stage=from_stage,
        to_stage=to_stage,
        comment=comment,
        changed_by=actor,
        changed_at=changed_at,
        created_by=actor,
        updated_by=actor,
    )



def _upsert_single_related(instance, *, data: dict, actor_field: str, timestamp_field: str, user):
    is_new = instance.pk is None
    for field, value in data.items():
        setattr(instance, field, value)
    setattr(instance, actor_field, user)
    if not getattr(instance, timestamp_field):
        setattr(instance, timestamp_field, timezone.now())
    if is_new:
        instance.created_by = user
    instance.updated_by = user
    instance.full_clean()
    instance.save()
    return instance, is_new


@transaction.atomic
def create_anomaly(*, user, data: dict, request_id: str = "") -> Anomaly:
    if not _can_create_anomaly(user):
        raise PermissionDenied("No tiene permisos para registrar anomalias.")

    reporter = data.pop("reporter", user)
    registration_comment = data.pop("registration_comment", "Registro inicial de la anomalia.") or "Registro inicial de la anomalia."
    code = data.pop("code", "") or generate_anomaly_code()

    if getattr(user, "access_level", "") != "usuario_activo":
        _ensure_scope(data["site"].pk, data["area"].pk, user)

    now = timezone.now()
    anomaly = Anomaly(
        **data,
        code=code,
        reporter=reporter,
        current_status=AnomalyStatus.REGISTERED,
        current_stage=AnomalyStage.REGISTRATION,
        last_transition_at=now,
        created_by=user,
        updated_by=user,
    )
    anomaly.full_clean()
    anomaly.save()

    _ensure_default_participants(anomaly, user)
    _write_status_history(
        anomaly=anomaly,
        from_status=AnomalyStatus.REGISTERED,
        to_status=AnomalyStatus.REGISTERED,
        from_stage=AnomalyStage.REGISTRATION,
        to_stage=AnomalyStage.REGISTRATION,
        comment=registration_comment,
        actor=user,
        changed_at=now,
    )
    record_audit_event(
        entity=anomaly,
        action="anomaly.created",
        actor=user,
        after_data=snapshot_anomaly(anomaly),
        request_id=_request_id(request_id),
    )
    notify_anomaly_created(anomaly=anomaly, actor=user, request_id=request_id)
    return anomaly


@transaction.atomic
def update_anomaly(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> Anomaly:
    _require_permission(user, PERMISSION_EDIT_ANOMALY, "No tiene permisos para editar anomalias.")
    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    before = snapshot_anomaly(locked)

    next_site = data.get("site", locked.site)
    next_area = data.get("area", locked.area)
    _ensure_scope(next_site.pk, next_area.pk, user)

    severity_in_payload = "severity" in data
    previous_severity_id = locked.severity_id

    if severity_in_payload:
        access_level = getattr(user, "access_level", "")
        if not (user.is_superuser or access_level in {"administrador", "desarrollador"}):
            raise PermissionDenied("Solo usuarios ADMIN pueden clasificar anomalias.")

    for field, value in data.items():
        setattr(locked, field, value)

    transition_applied = False
    transition_from_status = locked.current_status
    transition_from_stage = locked.current_stage
    transition_comment = ""

    should_sync_classification = severity_in_payload and locked.severity_id is not None
    if should_sync_classification:
        severity_name = locked.severity.name
        locked.classification_summary = f"Criterio de clasificacion aplicado: {severity_name}."

        if locked.current_status not in {AnomalyStatus.CANCELLED, AnomalyStatus.CLOSED} and locked.current_stage in {
            AnomalyStage.REGISTRATION,
            AnomalyStage.CONTAINMENT,
            AnomalyStage.INITIAL_VERIFICATION,
        }:
            transition_applied = True
            transition_from_status = locked.current_status
            transition_from_stage = locked.current_stage
            locked.current_stage = AnomalyStage.CLASSIFICATION
            locked.current_status = resolve_status_for_stage(AnomalyStage.CLASSIFICATION)
            locked.last_transition_at = timezone.now()
            transition_comment = f"Se registra verificacion inicial y clasificacion: {severity_name}."

    severity_changed = severity_in_payload and previous_severity_id != locked.severity_id

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()
    _ensure_default_participants(locked, user)

    if should_sync_classification:
        now = timezone.now()
        verification_summary = "Verificacion inicial registrada en seguimiento de anomalias."

        verification = _get_related_or_none(locked, "initial_verification")
        if verification is None:
            verification = AnomalyInitialVerification(
                anomaly=locked,
                verified_by=user,
                verified_at=now,
                summary=verification_summary,
                created_by=user,
                updated_by=user,
            )
        else:
            verification.verified_by = user
            if not verification.verified_at:
                verification.verified_at = now
            if not (verification.summary or "").strip():
                verification.summary = verification_summary
            verification.updated_by = user
        verification.full_clean()
        verification.save()
        _ensure_participant_role(
            anomaly=locked,
            participant_user=user,
            role=ParticipantRole.VERIFIER,
            actor=user,
            note="Participa como verificador de la etapa inicial.",
        )


        classification_summary = locked.classification_summary or f"Criterio de clasificacion aplicado: {locked.severity.name}."
        classification = _get_related_or_none(locked, "classification")
        if classification is None:
            classification = AnomalyClassification(
                anomaly=locked,
                classified_by=user,
                classified_at=now,
                summary=classification_summary,
                created_by=user,
                updated_by=user,
            )
        else:
            classification.classified_by = user
            if not classification.classified_at:
                classification.classified_at = now
            classification.summary = classification_summary
            classification.updated_by = user
        classification.full_clean()
        classification.save()

    if transition_applied:
        _write_status_history(
            anomaly=locked,
            from_status=transition_from_status,
            to_status=locked.current_status,
            from_stage=transition_from_stage,
            to_stage=locked.current_stage,
            comment=transition_comment,
            actor=user,
            changed_at=locked.last_transition_at or timezone.now(),
        )

    record_audit_event(
        entity=locked,
        action="anomaly.classification_applied" if severity_changed else "anomaly.updated",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked),
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def add_comment(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyComment:
    if not data.get("body", "").strip():
        raise ValidationError({"body": "El comentario no puede estar vacio."})

    comment = AnomalyComment(
        anomaly=anomaly,
        body=data["body"],
        comment_type=data.get("comment_type", AnomalyComment._meta.get_field("comment_type").default),
        author=user,
        created_by=user,
        updated_by=user,
    )
    comment.full_clean()
    comment.save()

    record_audit_event(
        entity=anomaly,
        action="anomaly.comment_added",
        actor=user,
        after_data={"comment_id": str(comment.pk), "comment_type": comment.comment_type, "body": comment.body},
        request_id=_request_id(request_id),
    )
    return comment


@transaction.atomic
def add_attachment(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyAttachment:
    _require_any_permission(
        user,
        {PERMISSION_EDIT_ANOMALY, PERMISSION_CREATE_ANOMALY, PERMISSION_ANALYZE_ANOMALY},
        "No tiene permisos para adjuntar evidencia.",
    )
    file_obj = data["file"]
    attachment = AnomalyAttachment(
        anomaly=anomaly,
        file=file_obj,
        original_name=data.get("original_name") or getattr(file_obj, "name", "archivo"),
        content_type=data.get("content_type") or getattr(file_obj, "content_type", ""),
        uploaded_by=user,
        created_by=user,
        updated_by=user,
    )
    attachment.full_clean()
    attachment.save()

    record_audit_event(
        entity=anomaly,
        action="anomaly.attachment_added",
        actor=user,
        after_data={"attachment_id": str(attachment.pk), "original_name": attachment.original_name},
        request_id=_request_id(request_id),
    )
    return attachment


@transaction.atomic
def add_participant(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyParticipant:
    _require_any_permission(
        user,
        {PERMISSION_EDIT_ANOMALY, PERMISSION_ANALYZE_ANOMALY, PERMISSION_ASSIGN_ACTION},
        "No tiene permisos para gestionar participantes.",
    )
    participant, created = AnomalyParticipant.objects.get_or_create(
        anomaly=anomaly,
        user=data["user"],
        role=data["role"],
        defaults={"note": data.get("note", ""), "created_by": user, "updated_by": user},
    )
    if not created:
        participant.note = data.get("note", participant.note)
        participant.updated_by = user
        participant.full_clean()
        participant.save()

    record_audit_event(
        entity=anomaly,
        action="anomaly.participant_added" if created else "anomaly.participant_updated",
        actor=user,
        after_data={"participant_id": str(participant.pk), "user_id": str(participant.user_id), "role": participant.role},
        request_id=_request_id(request_id),
    )
    if created:
        notify_participation_request(anomaly=anomaly, participant=participant, actor=user, request_id=request_id)
    return participant


@transaction.atomic
def save_initial_verification(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyInitialVerification:
    _require_permission(user, PERMISSION_CLASSIFY_ANOMALY, "No tiene permisos para registrar la verificacion inicial.")
    verification = _get_related_or_none(anomaly, "initial_verification") or AnomalyInitialVerification(anomaly=anomaly)
    verification, created = _upsert_single_related(
        verification,
        data=data,
        actor_field="verified_by",
        timestamp_field="verified_at",
        user=user,
    )
    _ensure_participant_role(
        anomaly=anomaly,
        participant_user=user,
        role=ParticipantRole.VERIFIER,
        actor=user,
        note="Participa como verificador de la etapa inicial.",
    )
    record_audit_event(
        entity=anomaly,
        action="anomaly.initial_verification_created" if created else "anomaly.initial_verification_updated",
        actor=user,
        after_data={"verification_id": str(verification.pk), "verified_at": verification.verified_at},
        request_id=_request_id(request_id),
    )
    return verification


@transaction.atomic
def save_classification(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyClassification:
    _require_permission(user, PERMISSION_CLASSIFY_ANOMALY, "No tiene permisos para clasificar la anomalia.")
    classification = _get_related_or_none(anomaly, "classification") or AnomalyClassification(anomaly=anomaly)
    classification, created = _upsert_single_related(
        classification,
        data=data,
        actor_field="classified_by",
        timestamp_field="classified_at",
        user=user,
    )
    anomaly.classification_summary = classification.summary
    anomaly.updated_by = user
    _bump_version(anomaly)
    anomaly.save(update_fields=["classification_summary", "updated_by", "row_version", "updated_at"])

    record_audit_event(
        entity=anomaly,
        action="anomaly.classification_created" if created else "anomaly.classification_updated",
        actor=user,
        after_data={"classification_id": str(classification.pk), "classified_at": classification.classified_at},
        request_id=_request_id(request_id),
    )
    return classification


@transaction.atomic
def save_cause_analysis(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyCauseAnalysis:
    _require_permission(user, PERMISSION_ANALYZE_ANOMALY, "No tiene permisos para registrar el analisis de causa.")
    analysis = _get_related_or_none(anomaly, "cause_analysis") or AnomalyCauseAnalysis(anomaly=anomaly)
    analysis, created = _upsert_single_related(
        analysis,
        data=data,
        actor_field="analyzed_by",
        timestamp_field="analyzed_at",
        user=user,
    )
    anomaly.root_cause_summary = analysis.root_cause or analysis.summary
    anomaly.updated_by = user
    _bump_version(anomaly)
    anomaly.save(update_fields=["root_cause_summary", "updated_by", "row_version", "updated_at"])

    record_audit_event(
        entity=anomaly,
        action="anomaly.cause_analysis_created" if created else "anomaly.cause_analysis_updated",
        actor=user,
        after_data={"analysis_id": str(analysis.pk), "method_used": analysis.method_used},
        request_id=_request_id(request_id),
    )
    return analysis


@transaction.atomic
def add_proposal(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyProposal:
    _require_permission(user, PERMISSION_ANALYZE_ANOMALY, "No tiene permisos para registrar propuestas.")
    proposal = AnomalyProposal(
        anomaly=anomaly,
        title=data["title"],
        description=data["description"],
        proposed_by=user,
        proposed_at=data.get("proposed_at") or timezone.now(),
        is_selected=data.get("is_selected", False),
        sequence=data.get("sequence") or (anomaly.proposals.count() + 1),
        created_by=user,
        updated_by=user,
    )
    proposal.full_clean()
    proposal.save()

    record_audit_event(
        entity=anomaly,
        action="anomaly.proposal_added",
        actor=user,
        after_data={"proposal_id": str(proposal.pk), "title": proposal.title, "sequence": proposal.sequence},
        request_id=_request_id(request_id),
    )
    return proposal


@transaction.atomic
def record_effectiveness_check(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyEffectivenessCheck:
    _require_permission(
        user,
        PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
        "No tiene permisos para registrar la verificacion de eficacia.",
    )
    check = AnomalyEffectivenessCheck(
        anomaly=anomaly,
        verified_by=user,
        verified_at=data.get("verified_at") or timezone.now(),
        is_effective=data["is_effective"],
        evidence_summary=data.get("evidence_summary", ""),
        comment=data["comment"],
        recommended_stage=data.get("recommended_stage", ""),
        created_by=user,
        updated_by=user,
    )
    check.full_clean()
    check.save()

    anomaly.effectiveness_summary = check.comment
    anomaly.updated_by = user
    _bump_version(anomaly)
    anomaly.save(update_fields=["effectiveness_summary", "updated_by", "row_version", "updated_at"])

    record_audit_event(
        entity=anomaly,
        action="anomaly.effectiveness_checked",
        actor=user,
        after_data={
            "check_id": str(check.pk),
            "is_effective": check.is_effective,
            "recommended_stage": check.recommended_stage,
        },
        request_id=_request_id(request_id),
    )
    return check


@transaction.atomic
def save_learning(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyLearning:
    _require_permission(user, PERMISSION_CLOSE_ANOMALY, "No tiene permisos para registrar aprendizaje.")
    learning = _get_related_or_none(anomaly, "learning") or AnomalyLearning(anomaly=anomaly)
    learning, created = _upsert_single_related(
        learning,
        data=data,
        actor_field="recorded_by",
        timestamp_field="recorded_at",
        user=user,
    )
    record_audit_event(
        entity=anomaly,
        action="anomaly.learning_created" if created else "anomaly.learning_updated",
        actor=user,
        after_data={"learning_id": str(learning.pk), "recorded_at": learning.recorded_at},
        request_id=_request_id(request_id),
    )
    return learning


@transaction.atomic
def transition_anomaly(*, anomaly: Anomaly, user, target_stage: str | None = None, target_status: str | None = None, comment: str, request_id: str = "") -> Anomaly:
    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    _ensure_scope(locked.site_id, locked.area_id, user)

    if target_status == AnomalyStatus.CANCELLED:
        target_stage = target_stage or locked.current_stage
    elif not target_stage:
        raise ValidationError({"target_stage": "Debe indicar la etapa destino."})

    reopened = target_status == AnomalyStatus.REOPENED
    resolved_target_status = target_status or resolve_status_for_stage(target_stage, reopened=reopened)

    ensure_transition_permission(user=user, target_status=resolved_target_status, target_stage=target_stage)
    validate_transition(anomaly=locked, target_stage=target_stage, target_status=resolved_target_status, comment=comment)

    before = snapshot_anomaly(locked)
    now = timezone.now()
    previous_status = locked.current_status
    previous_stage = locked.current_stage

    locked.current_stage = target_stage
    locked.current_status = resolved_target_status
    locked.last_transition_at = now
    locked.updated_by = user

    if target_stage == AnomalyStage.CLOSURE:
        locked.closed_at = now
        locked.closure_comment = comment
    elif resolved_target_status == AnomalyStatus.CANCELLED:
        locked.cancellation_reason = comment
    elif resolved_target_status == AnomalyStatus.REOPENED:
        locked.closed_at = None
        locked.reopened_count += 1
    elif previous_status == AnomalyStatus.CLOSED and target_stage != AnomalyStage.STANDARDIZATION_AND_LEARNING:
        locked.closed_at = None

    _bump_version(locked)
    locked.full_clean()
    locked.save()

    _write_status_history(
        anomaly=locked,
        from_status=previous_status,
        to_status=locked.current_status,
        from_stage=previous_stage,
        to_stage=locked.current_stage,
        comment=comment,
        actor=user,
        changed_at=now,
    )
    record_audit_event(
        entity=locked,
        action="anomaly.transitioned",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked) | {"comment": comment},
        request_id=_request_id(request_id),
    )
    return locked







