from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.services.access_policy import (
    can_create_anomaly,
    can_manage_assigned_process,
    has_global_access,
    is_assignable_process_manager,
)
from apps.actions.models import Treatment, TreatmentEffectivenessValidationResult, TreatmentStatus
from apps.audit.services import record_audit_event
from apps.notifications.services import (
    complete_observation_effectiveness_assignment,
    notify_anomaly_created,
    notify_finding_management_assigned,
    notify_observation_effectiveness_assigned,
    notify_participation_request,
)
from apps.anomalies.models import (
    AffectedOrder,
    Anomaly,
    AnomalyAttachment,
    AnomalyCauseAnalysis,
    AnomalyClassification,
    AnomalyCodeReservation,
    AnomalyComment,
    AnomalyEffectivenessCheck,
    AnomalyInitialVerification,
    AnomalyImmediateAction,
    AnomalyLearning,
    AnomalyParticipant,
    AnomalyProposal,
    AnomalyStage,
    AnomalyStatus,
    AnomalyStatusHistory,
    ObservationResolutionPath,
    ParticipantRole,
)
from apps.anomalies.services.classification_rules import (
    can_modify_classification,
    can_unlock_classification_change,
    is_immediate_action_anomaly,
    stage_allows_classification_change,
)
from apps.anomalies.services.workflow import (
    ensure_transition_permission,
    resolve_status_for_stage,
    validate_transition,
)
from apps.catalog.models import OrderType, Priority
from common.upload_validation import normalized_upload_content_type, validate_evidence_file



def _require_admin_access_level(user, message: str) -> None:
    if has_global_access(user):
        return
    raise PermissionDenied(message)


def _is_admin_access_level(user) -> bool:
    return has_global_access(user)


def _observation_responsible_id(anomaly: Anomaly, immediate_action: AnomalyImmediateAction | None = None):
    if immediate_action is not None and getattr(immediate_action, "responsible_id", None):
        return immediate_action.responsible_id
    return getattr(anomaly, "owner_id", None)


def _can_manage_observation(anomaly: Anomaly, user, immediate_action: AnomalyImmediateAction | None = None) -> bool:
    responsible_id = _observation_responsible_id(anomaly, immediate_action)
    return can_manage_assigned_process(user, responsible_id)


def _require_observation_manager(anomaly: Anomaly, user, immediate_action: AnomalyImmediateAction | None = None) -> None:
    if _can_manage_observation(anomaly, user, immediate_action):
        return
    raise PermissionDenied("Solo el responsable asignado o usuarios ADMIN pueden gestionar Observacion.")


def _can_create_anomaly(user) -> bool:
    return can_create_anomaly(user)



def _ensure_scope(site_id, area_id, user) -> None:
    # Sitio y sector son metadatos descriptivos del hecho, no alcance de autorizacion.
    return None


def _require_anomaly_manager(anomaly: Anomaly, user, message: str = "Solo el responsable asignado o usuarios ADMIN pueden gestionar la anomalia.") -> None:
    if not can_manage_assigned_process(user, anomaly.owner_id):
        raise PermissionDenied(message)


def _require_anomaly_editor(anomaly: Anomaly, user) -> None:
    if has_global_access(user):
        return
    if anomaly.reporter_id == getattr(user, "id", None):
        return
    if can_manage_assigned_process(user, anomaly.owner_id):
        return
    raise PermissionDenied("Solo quien informo la anomalia, su responsable o usuarios ADMIN pueden editarla.")



def _bump_version(instance) -> None:
    instance.row_version = (instance.row_version or 0) + 1



def _request_id(value: str | None) -> str:
    return (value or "").strip()



def _get_related_or_none(instance, attr_name: str):
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return None


def is_anomaly_locked_by_effective_treatment(anomaly: Anomaly) -> bool:
    return (
        Treatment.objects.filter(
            anomaly_links__anomaly=anomaly,
            status=TreatmentStatus.COMPLETED,
            effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
        ).exists()
        or Treatment.objects.filter(
            primary_anomaly=anomaly,
            status=TreatmentStatus.COMPLETED,
            effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
        ).exists()
    )


def _ensure_anomaly_is_editable(anomaly: Anomaly) -> None:
    if is_anomaly_locked_by_effective_treatment(anomaly):
        raise ValidationError(
            {"anomaly": "La anomalia esta cerrada por un tratamiento validado como eficaz y no admite modificaciones."}
        )



def snapshot_anomaly(anomaly: Anomaly) -> dict:
    return {
        "id": str(anomaly.pk),
        "code": anomaly.code,
        "title": anomaly.title,
        "current_status": anomaly.current_status,
        "current_stage": anomaly.current_stage,
        "site_id": str(anomaly.site_id) if anomaly.site_id else "",
        "area_id": str(anomaly.area_id) if anomaly.area_id else "",
        "imputed_area_id": str(anomaly.imputed_area_id) if anomaly.imputed_area_id else "",
        "line_id": str(anomaly.line_id) if anomaly.line_id else "",
        "reporter_id": str(anomaly.reporter_id) if anomaly.reporter_id else "",
        "owner_id": str(anomaly.owner_id) if anomaly.owner_id else "",
        "severity_id": str(anomaly.severity_id) if anomaly.severity_id else "",
        "priority_id": str(anomaly.priority_id) if anomaly.priority_id else "",
        "detected_at": anomaly.detected_at,
        "manufacturing_order_number": anomaly.manufacturing_order_number,
        "affected_quantity": anomaly.affected_quantity,
        "affected_orders": [
            {
                "order_type_id": str(item.order_type_id),
                "number": item.number,
                "quantity": item.quantity,
            }
            for item in anomaly.affected_orders.select_related("order_type").all()
        ],
        "affected_process": anomaly.affected_process,
        "last_transition_at": anomaly.last_transition_at,
        "observation_resolution_path": anomaly.observation_resolution_path,
        "classification_change_count": anomaly.classification_change_count,
        "classification_change_unlocked": anomaly.classification_change_unlocked,
        "closed_at": anomaly.closed_at,
    }


def _legacy_affected_orders(number: str, quantity: int | None):
    normalized_number = (number or "").strip()
    if not normalized_number:
        return []
    order_type = OrderType.objects.filter(code__iexact="OF", is_active=True).first()
    if order_type is None:
        raise ValidationError({"affected_orders": "Debe existir un tipo de orden OF activo para migrar el dato anterior."})
    return [{"order_type": order_type, "number": normalized_number, "quantity": quantity or 1}]


def _sync_legacy_order_fields(data: dict, affected_orders: list[dict]) -> None:
    if affected_orders:
        first = affected_orders[0]
        data["manufacturing_order_number"] = first["number"].strip()
        data["affected_quantity"] = first["quantity"]
        return
    data["manufacturing_order_number"] = ""
    data["affected_quantity"] = None


def _replace_affected_orders(*, anomaly: Anomaly, affected_orders: list[dict], user) -> None:
    anomaly.affected_orders.all().delete()
    for item in affected_orders:
        affected_order = AffectedOrder(
            anomaly=anomaly,
            order_type=item["order_type"],
            number=item["number"].strip(),
            quantity=item["quantity"],
            created_by=user,
            updated_by=user,
        )
        affected_order.full_clean()
        affected_order.save()



def _build_visible_code(year: int, sequence: int) -> str:
    return f"{year}{sequence:04d}"


def _extract_sequence_from_code(code: str | None, *, year: int) -> int:
    if not code:
        return 0
    prefix = str(year)
    if not code.startswith(prefix):
        return 0
    suffix = code[len(prefix):]
    if len(suffix) != 4 or not suffix.isdigit():
        return 0
    return int(suffix)


def _reservation_expiration_cutoff():
    minutes = max(1, int(getattr(settings, "ANOMALY_CODE_RESERVATION_MINUTES", 30)))
    return timezone.now() - timedelta(minutes=minutes)


def _release_expired_code_reservations() -> None:
    AnomalyCodeReservation.objects.filter(
        anomaly__isnull=True,
        consumed_at__isnull=True,
        created_at__lt=_reservation_expiration_cutoff(),
    ).delete()


def _reservation_is_expired(reservation: AnomalyCodeReservation) -> bool:
    return reservation.created_at < _reservation_expiration_cutoff()


def _next_sequence_for_year(year: int) -> int:
    prefix = str(year)
    used_sequences = {
        _extract_sequence_from_code(code, year=year)
        for code in Anomaly.objects.filter(code__startswith=prefix, code__regex=rf"^{year}\\d{{4}}$")
        .values_list("code", flat=True)
    }
    reserved_sequences = set(
        AnomalyCodeReservation.objects.filter(year=year, anomaly__isnull=True, consumed_at__isnull=True)
        .values_list("sequence", flat=True)
    )
    unavailable_sequences = used_sequences | reserved_sequences

    for sequence in range(1, 10001):
        if sequence not in unavailable_sequences:
            return sequence

    raise ValidationError("No hay codigos visibles disponibles para el año actual.")


def _code_is_reserved_or_used(code: str) -> bool:
    return (
        Anomaly.objects.filter(code=code).exists()
        or AnomalyCodeReservation.objects.filter(code=code, anomaly__isnull=True, consumed_at__isnull=True).exists()
    )


def generate_anomaly_code() -> str:
    _release_expired_code_reservations()
    year = timezone.localdate().year
    sequence = _next_sequence_for_year(year)

    for _ in range(10000):
        candidate = _build_visible_code(year, sequence)
        if not _code_is_reserved_or_used(candidate):
            return candidate
        sequence += 1

    raise ValidationError("No se pudo generar un codigo visible para la anomalia.")


@transaction.atomic
def reserve_anomaly_code(*, user) -> AnomalyCodeReservation:
    if not _can_create_anomaly(user):
        raise PermissionDenied("No tiene permisos para reservar codigos de anomalia.")

    _release_expired_code_reservations()

    existing = (
        AnomalyCodeReservation.objects.select_for_update()
        .filter(reserved_by=user, anomaly__isnull=True, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if existing and not _reservation_is_expired(existing) and not Anomaly.objects.filter(code=existing.code).exists():
        return existing
    if existing and _reservation_is_expired(existing):
        existing.delete()

    year = timezone.localdate().year
    sequence = _next_sequence_for_year(year)

    for _ in range(10000):
        candidate = _build_visible_code(year, sequence)
        if _code_is_reserved_or_used(candidate):
            sequence += 1
            continue

        try:
            return AnomalyCodeReservation.objects.create(
                code=candidate,
                year=year,
                sequence=sequence,
                reserved_by=user,
                created_by=user,
                updated_by=user,
            )
        except IntegrityError:
            sequence += 1

    raise ValidationError("No se pudo reservar un codigo visible para la anomalia.")

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


def _user_label(user) -> str:
    return user.full_name or user.username or user.email or str(user.pk)


def _write_status_history(
    *,
    anomaly: Anomaly,
    from_status: str,
    to_status: str,
    from_stage: str,
    to_stage: str,
    comment: str,
    actor,
    changed_at,
    evidence_note: str = "",
):
    return AnomalyStatusHistory.objects.create(
        anomaly=anomaly,
        from_status=from_status,
        to_status=to_status,
        from_stage=from_stage,
        to_stage=to_stage,
        comment=comment,
        evidence_note=evidence_note,
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
    reservation_id = data.pop("code_reservation_id", None)
    requested_code = (data.pop("code", "") or "").strip()
    affected_orders = data.pop("affected_orders", None)
    if affected_orders is None:
        affected_orders = _legacy_affected_orders(
            data.get("manufacturing_order_number", ""),
            data.get("affected_quantity"),
        )
    _sync_legacy_order_fields(data, affected_orders)

    reservation = None
    if reservation_id:
        reservation = (
            AnomalyCodeReservation.objects.select_for_update()
            .filter(pk=reservation_id, reserved_by=user, anomaly__isnull=True, consumed_at__isnull=True)
            .first()
        )
        if reservation is None:
            raise ValidationError({"code_reservation_id": "La reserva de codigo no existe o ya fue consumida."})
        if _reservation_is_expired(reservation):
            expired_code = reservation.code
            reservation.delete()
            raise ValidationError(
                {"code_reservation_id": f"La reserva del codigo {expired_code} vencio. Solicite un nuevo codigo."}
            )
        code = reservation.code
    elif requested_code:
        code = requested_code
    else:
        code = generate_anomaly_code()

    if Anomaly.objects.filter(code=code).exists():
        raise ValidationError({"code": "El codigo de anomalia ya existe. Solicite una nueva reserva."})

    if reservation is None and AnomalyCodeReservation.objects.filter(code=code, anomaly__isnull=True, consumed_at__isnull=True).exists():
        raise ValidationError({"code": "El codigo esta reservado para otra carga. Solicite una nueva reserva."})

    if not data.get("priority"):
        default_priority = Priority.objects.filter(is_active=True).order_by("sort_order", "name").first()
        if default_priority is None:
            raise ValidationError({"priority": "Debe existir al menos un criterio operativo activo para registrar la anomalia."})
        data["priority"] = default_priority

    if data.get("area") and data["area"].site_id != data["site"].pk:
        data["site"] = data["area"].site

    if getattr(user, "access_level", "") != "usuario_activo":
        _ensure_scope(data["site"].pk, data["area"].pk, user)

    data.setdefault("imputed_area", data.get("area"))

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
    _replace_affected_orders(anomaly=anomaly, affected_orders=affected_orders, user=user)

    if reservation is not None:
        reservation.anomaly = anomaly
        reservation.consumed_at = now
        reservation.consumed_by = user
        reservation.updated_by = user
        reservation.full_clean()
        reservation.save(update_fields=["anomaly", "consumed_at", "consumed_by", "updated_by", "updated_at"])

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
    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    _require_anomaly_editor(locked, user)
    _ensure_anomaly_is_editable(locked)
    before = snapshot_anomaly(locked)
    classification_responsible = data.pop("classification_responsible", None)
    classification_reason = (data.pop("classification_reason", "") or "").strip()
    affected_orders = data.pop("affected_orders", None)
    legacy_order_changed = "manufacturing_order_number" in data or "affected_quantity" in data
    if affected_orders is not None:
        _sync_legacy_order_fields(data, affected_orders)

    next_site = data.get("site", locked.site)
    next_area = data.get("area", locked.area)
    _ensure_scope(next_site.pk, next_area.pk, user)

    severity_in_payload = "severity" in data
    previous_severity_id = locked.severity_id

    if severity_in_payload:
        _require_admin_access_level(user, "Solo usuarios ADMIN pueden realizar Revisión de hallazgos de anomalias.")

    for field, value in data.items():
        setattr(locked, field, value)

    transition_from_status = locked.current_status
    transition_from_stage = locked.current_stage
    transition_comment = ""
    now = timezone.now()

    severity_changed = severity_in_payload and previous_severity_id != locked.severity_id
    if severity_changed:
        if locked.severity_id is None:
            raise ValidationError({"severity": "Debe seleccionar una Revisión de hallazgos valida."})

        if not can_modify_classification(locked):
            raise ValidationError({"severity": "No se puede modificar la Revisión de hallazgos."})

        if previous_severity_id is not None:
            locked.classification_change_count = (locked.classification_change_count or 0) + 1
            if locked.classification_change_unlocked:
                locked.classification_change_unlocked = False

    should_sync_classification = severity_in_payload and locked.severity_id is not None
    if should_sync_classification:
        severity_name = locked.severity.name
        closes_as_invalid = bool(getattr(locked.severity, "closes_anomaly_as_invalid", False))
        requires_responsible = bool(getattr(locked.severity, "requires_classification_responsible", True))

        if closes_as_invalid:
            if not classification_reason:
                raise ValidationError({"classification_reason": "Debe registrar una observacion o motivo para clasificar como Invalida."})
        elif requires_responsible and classification_responsible is None:
            raise ValidationError({"classification_responsible": "Debe seleccionar un responsable para continuar el flujo."})
        elif classification_responsible is not None and not is_assignable_process_manager(classification_responsible):
            raise ValidationError(
                {"classification_responsible": "El responsable debe tener nivel Mando medio, Administrador o Desarrollador."}
            )
        locked.classification_summary = f"Criterio de Revisión de hallazgos aplicado: {severity_name}."

        if closes_as_invalid:
            transition_from_status = locked.current_status
            transition_from_stage = locked.current_stage
            locked.current_stage = AnomalyStage.CLOSURE
            locked.current_status = AnomalyStatus.CLOSED
            locked.closed_at = now
            locked.last_transition_at = now
            locked.closure_comment = classification_reason
            locked.result_summary = classification_reason
            transition_comment = f"Revision de hallazgos: {severity_name}. Anomalia cerrada por administracion."
        elif classification_responsible is not None:
            locked.owner = classification_responsible

        if not closes_as_invalid and locked.current_status not in {AnomalyStatus.CANCELLED, AnomalyStatus.CLOSED} and locked.current_stage in {
            AnomalyStage.REGISTRATION,
            AnomalyStage.CONTAINMENT,
            AnomalyStage.INITIAL_VERIFICATION,
        }:
            transition_from_status = locked.current_status
            transition_from_stage = locked.current_stage
            locked.current_stage = AnomalyStage.CLASSIFICATION
            locked.current_status = resolve_status_for_stage(AnomalyStage.CLASSIFICATION)
            locked.last_transition_at = now
            transition_comment = f"Se registra verificacion inicial y Revisión de hallazgos: {severity_name}."
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()
    if affected_orders is not None:
        _replace_affected_orders(anomaly=locked, affected_orders=affected_orders, user=user)
    elif legacy_order_changed:
        legacy_orders = _legacy_affected_orders(locked.manufacturing_order_number, locked.affected_quantity)
        _replace_affected_orders(anomaly=locked, affected_orders=legacy_orders, user=user)
    _ensure_default_participants(locked, user)

    if should_sync_classification:
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


        classification_summary = locked.classification_summary or f"Criterio de Revisión de hallazgos aplicado: {locked.severity.name}."
        if closes_as_invalid and classification_reason:
            classification_summary = f"{classification_summary} Motivo: {classification_reason}"
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
            classification.classified_at = now
            classification.summary = classification_summary
            classification.updated_by = user
        classification.containment_required = not closes_as_invalid
        classification.requires_action_plan = not closes_as_invalid
        classification.requires_effectiveness_verification = not closes_as_invalid
        classification.full_clean()
        classification.save()

        if classification_responsible is not None and not closes_as_invalid:
            _ensure_participant_role(
                anomaly=locked,
                participant_user=classification_responsible,
                role=ParticipantRole.OWNER,
                actor=user,
                note=f"Responsable asignado por Revision de hallazgos: {locked.severity.name}.",
            )

    if should_sync_classification:
        evidence_lines = [
            f"Clasificacion: {locked.severity.name}",
            f"Confirmado por: {_user_label(user)}",
            f"Fecha/hora: {now.isoformat()}",
        ]
        if closes_as_invalid:
            evidence_lines.append("Resultado: Invalida")
            evidence_lines.append(f"Motivo: {classification_reason}")
        elif classification_responsible is not None:
            evidence_lines.append(f"Responsable asignado: {_user_label(classification_responsible)}")
        evidence_lines.extend(
            [
                f"Estado anterior: {transition_from_status}",
                f"Estado nuevo: {locked.current_status}",
                f"Etapa anterior: {transition_from_stage}",
                f"Etapa nueva: {locked.current_stage}",
            ]
        )
        _write_status_history(
            anomaly=locked,
            from_status=transition_from_status,
            to_status=locked.current_status,
            from_stage=transition_from_stage,
            to_stage=locked.current_stage,
            comment=transition_comment or f"Revision de hallazgos confirmada: {locked.severity.name}.",
            evidence_note="\n".join(evidence_lines),
            actor=user,
            changed_at=locked.last_transition_at or now,
        )

    record_audit_event(
        entity=locked,
        action="anomaly.classification_applied" if severity_changed else "anomaly.updated",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked),
        request_id=_request_id(request_id),
    )
    if should_sync_classification:
        notify_finding_management_assigned(
            anomaly=locked,
            responsible=None if closes_as_invalid else classification_responsible,
            actor=user,
            request_id=request_id,
        )
    return locked


@transaction.atomic
def add_comment(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyComment:
    _ensure_anomaly_is_editable(anomaly)
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
    _ensure_anomaly_is_editable(anomaly)
    can_attach = bool(
        has_global_access(user)
        or anomaly.reporter_id == getattr(user, "id", None)
        or can_manage_assigned_process(user, anomaly.owner_id)
    )
    if not can_attach:
        if is_immediate_action_anomaly(anomaly):
            _require_observation_manager(anomaly, user, _get_related_or_none(anomaly, "immediate_action"))
        else:
            raise PermissionDenied("No tiene permisos para adjuntar evidencia.")
    file_obj = data["file"]
    validate_evidence_file(file_obj)
    attachment = AnomalyAttachment(
        anomaly=anomaly,
        file=file_obj,
        original_name=data.get("original_name") or getattr(file_obj, "name", "archivo"),
        content_type=normalized_upload_content_type(file_obj),
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
    _write_status_history(
        anomaly=anomaly,
        from_status=anomaly.current_status,
        to_status=anomaly.current_status,
        from_stage=anomaly.current_stage,
        to_stage=anomaly.current_stage,
        comment=f"Evidencia cargada: {attachment.original_name}.",
        evidence_note=f"Archivo: {attachment.original_name}\nTipo: {attachment.content_type or 'sin tipo'}",
        actor=user,
        changed_at=timezone.now(),
    )
    return attachment


@transaction.atomic
def add_participant(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyParticipant:
    _ensure_anomaly_is_editable(anomaly)
    _require_anomaly_manager(anomaly, user, "Solo el responsable asignado o usuarios ADMIN pueden gestionar participantes.")
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
    _ensure_anomaly_is_editable(anomaly)
    _require_admin_access_level(user, "Solo usuarios ADMIN pueden registrar la verificacion inicial.")
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
    _ensure_anomaly_is_editable(anomaly)
    _require_admin_access_level(user, "Solo usuarios ADMIN pueden realizar Revisión de hallazgos de anomalias.")
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
def unlock_classification_change(*, anomaly: Anomaly, user, request_id: str = "") -> Anomaly:
    _ensure_anomaly_is_editable(anomaly)
    _require_admin_access_level(user, "Solo usuarios ADMIN pueden habilitar cambio de Revisión de hallazgos.")
    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)

    if not stage_allows_classification_change(locked):
        raise ValidationError({"severity": "No se puede modificar la Revisión de hallazgos."})

    if locked.severity_id is None:
        raise ValidationError({"severity": "La anomalia no tiene Revisión de hallazgos registrada."})

    if not can_unlock_classification_change(locked):
        return locked

    before = snapshot_anomaly(locked)
    now = timezone.now()

    locked.classification_change_unlocked = True
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save(update_fields=["classification_change_unlocked", "updated_by", "row_version", "updated_at"])

    _write_status_history(
        anomaly=locked,
        from_status=locked.current_status,
        to_status=locked.current_status,
        from_stage=locked.current_stage,
        to_stage=locked.current_stage,
        comment="Se habilita el cambio de Revisión de hallazgos.",
        actor=user,
        changed_at=now,
    )

    record_audit_event(
        entity=locked,
        action="anomaly.classification_change_unlocked",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked),
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def save_cause_analysis(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyCauseAnalysis:
    _ensure_anomaly_is_editable(anomaly)
    _require_anomaly_manager(anomaly, user)
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
    _ensure_anomaly_is_editable(anomaly)
    _require_anomaly_manager(anomaly, user)
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
    _ensure_anomaly_is_editable(anomaly)
    user_id = getattr(user, "id", None)
    is_assigned = bool(
        user_id
        and (
            anomaly.primary_treatments.filter(effectiveness_responsible_id=user_id).exists()
            or Treatment.objects.filter(
                anomaly_links__anomaly=anomaly,
                effectiveness_responsible_id=user_id,
            ).exists()
            or _observation_responsible_id(anomaly) == user_id
        )
    )
    if not is_assigned:
        raise PermissionDenied("Solo el usuario asignado puede registrar la verificacion de eficacia.")
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
    _ensure_anomaly_is_editable(anomaly)
    _require_anomaly_manager(anomaly, user)
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




def _ensure_observation_path_available(locked: Anomaly) -> None:
    if not is_immediate_action_anomaly(locked):
        raise ValidationError({"anomaly": "La anomalia no tiene Revision de hallazgos como Observacion."})
    if locked.observation_resolution_path == ObservationResolutionPath.TREATMENT:
        raise ValidationError({"anomaly": "La anomalia ya fue derivada a Tratamiento y no puede gestionarse como Observacion."})


def _get_observation_record(locked: Anomaly) -> AnomalyImmediateAction:
    return _get_related_or_none(locked, "immediate_action") or AnomalyImmediateAction(anomaly=locked)


@transaction.atomic
def save_observation_load(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyImmediateAction:
    _ensure_anomaly_is_editable(anomaly)

    required_fields = {
        "observation": "Debe registrar una observacion.",
        "responsible": "Debe seleccionar un responsable.",
        "action_date": "Debe indicar la fecha limite de ejecucion.",
    }
    for field_name, message in required_fields.items():
        value = data.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError({field_name: message})

    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    _ensure_observation_path_available(locked)
    immediate_action = _get_observation_record(locked)
    _require_observation_manager(locked, user, immediate_action if immediate_action.pk else None)
    if locked.owner_id and data["responsible"].pk != locked.owner_id:
        raise ValidationError({"responsible": "La Observacion debe gestionarla el responsable asignado en Revision de hallazgos."})
    if immediate_action.pk and immediate_action.responsible_id and data["responsible"].pk != immediate_action.responsible_id:
        raise ValidationError({"responsible": "No se puede cambiar el responsable de una Observacion ya cargada."})

    before = snapshot_anomaly(locked)
    previous_resolution_path = locked.observation_resolution_path

    immediate_action.observation = data["observation"].strip()
    immediate_action.responsible = data["responsible"]
    immediate_action.action_date = data["action_date"]
    if immediate_action.pk is None:
        immediate_action.created_by = user
    immediate_action.updated_by = user
    immediate_action.full_clean()
    immediate_action.save()

    _ensure_participant_role(
        anomaly=locked,
        participant_user=immediate_action.responsible,
        role=ParticipantRole.OWNER,
        actor=user,
        note="Responsable de Observacion.",
    )
    _ensure_participant_role(
        anomaly=locked,
        participant_user=user,
        role=ParticipantRole.VERIFIER,
        actor=user,
        note="Registra y verifica cierre por Observacion.",
    )

    now = timezone.now()
    previous_status = locked.current_status
    previous_stage = locked.current_stage
    locked.owner = immediate_action.responsible
    locked.observation_resolution_path = ObservationResolutionPath.OBSERVATION
    locked.containment_summary = immediate_action.observation
    locked.closed_at = None
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    _write_status_history(
        anomaly=locked,
        from_status=previous_status,
        to_status=locked.current_status,
        from_stage=previous_stage,
        to_stage=locked.current_stage,
        comment="Carga de Observacion confirmada.",
        evidence_note="\n".join(
            [
                f"Camino elegido: {ObservationResolutionPath.OBSERVATION}",
                f"Camino anterior: {previous_resolution_path or 'sin definir'}",
                f"Responsable: {_user_label(immediate_action.responsible)}",
                f"Fecha limite de ejecucion: {immediate_action.action_date.isoformat()}",
                f"Observacion: {immediate_action.observation}",
            ]
        ),
        actor=user,
        changed_at=now,
    )

    record_audit_event(
        entity=locked,
        action="anomaly.observation_loaded",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked) | {
            "immediate_action_id": str(immediate_action.pk),
            "observation_resolution_path": ObservationResolutionPath.OBSERVATION,
        },
        request_id=_request_id(request_id),
    )
    return immediate_action


@transaction.atomic
def save_observation_action_taken(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyImmediateAction:
    _ensure_anomaly_is_editable(anomaly)

    required_fields = {
        "action_completed_at": "Debe indicar la fecha de realizado.",
        "actions_taken": "Debe registrar el detalle de la accion.",
        "effectiveness_due_at": "Debe indicar la fecha de verificacion de eficacia.",
    }
    for field_name, message in required_fields.items():
        value = data.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError({field_name: message})

    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    _ensure_observation_path_available(locked)
    immediate_action = _get_related_or_none(locked, "immediate_action")
    if immediate_action is None:
        raise ValidationError({"observation": "Primero debe confirmar la carga de Observacion."})
    _require_observation_manager(locked, user, immediate_action)

    before = snapshot_anomaly(locked)
    previous_status = locked.current_status
    previous_stage = locked.current_stage
    now = timezone.now()

    immediate_action.action_completed_at = data["action_completed_at"]
    immediate_action.actions_taken = data["actions_taken"].strip()
    immediate_action.effectiveness_due_at = data["effectiveness_due_at"]
    immediate_action.effectiveness_verified_at = None
    immediate_action.effectiveness_is_effective = None
    immediate_action.effectiveness_comment = ""
    immediate_action.closure_comment = ""
    immediate_action.updated_by = user
    immediate_action.full_clean()
    immediate_action.save()

    locked.resolution_summary = immediate_action.actions_taken
    locked.current_stage = AnomalyStage.EFFECTIVENESS_VERIFICATION
    locked.current_status = AnomalyStatus.PENDING_VERIFICATION
    locked.closed_at = None
    locked.closure_comment = ""
    locked.last_transition_at = now
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    _write_status_history(
        anomaly=locked,
        from_status=previous_status,
        to_status=locked.current_status,
        from_stage=previous_stage,
        to_stage=locked.current_stage,
        comment="Acciones tomadas confirmadas.",
        evidence_note="\n".join(
            [
                f"Fecha de realizado: {immediate_action.action_completed_at.isoformat()}",
                f"Detalle de la accion: {immediate_action.actions_taken}",
                f"Fecha de verificacion de eficacia: {immediate_action.effectiveness_due_at.isoformat()}",
            ]
        ),
        actor=user,
        changed_at=now,
    )
    record_audit_event(
        entity=locked,
        action="anomaly.observation_action_taken",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked) | {"immediate_action_id": str(immediate_action.pk)},
        request_id=_request_id(request_id),
    )
    notify_observation_effectiveness_assigned(
        anomaly=locked,
        immediate_action=immediate_action,
        actor=user,
        request_id=request_id,
    )
    return immediate_action


@transaction.atomic
def verify_observation_effectiveness(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyImmediateAction:
    _ensure_anomaly_is_editable(anomaly)

    if data.get("effectiveness_is_effective") is None:
        raise ValidationError({"effectiveness_is_effective": "Debe indicar si fue eficaz."})
    if not data.get("effectiveness_verified_at"):
        raise ValidationError({"effectiveness_verified_at": "Debe indicar la fecha de verificacion de eficacia."})

    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    _ensure_observation_path_available(locked)
    immediate_action = _get_related_or_none(locked, "immediate_action")
    if immediate_action is None or not (immediate_action.actions_taken or "").strip():
        raise ValidationError({"actions_taken": "Primero debe confirmar una accion tomada."})
    if immediate_action.responsible_id != getattr(user, "id", None):
        raise PermissionDenied("Solo el responsable asignado puede verificar la eficacia de la Observacion.")

    before = snapshot_anomaly(locked)
    previous_status = locked.current_status
    previous_stage = locked.current_stage
    now = timezone.now()
    is_effective = bool(data["effectiveness_is_effective"])
    check_comment = (data.get("effectiveness_comment") or "").strip() or (
        "Observacion verificada como eficaz." if is_effective else "No eficaz. Queda abierta para nueva accion tomada."
    )

    immediate_action.effectiveness_verified_at = data["effectiveness_verified_at"]
    immediate_action.effectiveness_is_effective = is_effective
    immediate_action.effectiveness_comment = check_comment
    immediate_action.closure_comment = (data.get("closure_comment") or "").strip()
    immediate_action.updated_by = user
    immediate_action.full_clean()
    immediate_action.save()

    check = AnomalyEffectivenessCheck(
        anomaly=locked,
        verified_by=immediate_action.responsible,
        verified_at=immediate_action.effectiveness_verified_at,
        is_effective=is_effective,
        evidence_summary=immediate_action.actions_taken,
        comment=check_comment,
        recommended_stage="",
        created_by=user,
        updated_by=user,
    )
    check.full_clean()
    check.save()

    locked.result_summary = check_comment
    locked.effectiveness_summary = check_comment
    if is_effective:
        locked.current_stage = AnomalyStage.CLOSURE
        locked.current_status = AnomalyStatus.CLOSED
        locked.closed_at = now
        locked.closure_comment = immediate_action.closure_comment or "Cierre directo por Observacion eficaz."
        history_comment = "Verificacion de eficacia confirmada. Anomalia cerrada."
    else:
        locked.current_stage = AnomalyStage.EFFECTIVENESS_VERIFICATION
        locked.current_status = AnomalyStatus.PENDING_VERIFICATION
        locked.closed_at = None
        locked.closure_comment = ""
        history_comment = "Verificacion de eficacia No eficaz. La anomalia queda abierta para nueva accion tomada."

    locked.last_transition_at = now
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    _write_status_history(
        anomaly=locked,
        from_status=previous_status,
        to_status=locked.current_status,
        from_stage=previous_stage,
        to_stage=locked.current_stage,
        comment=history_comment,
        evidence_note="\n".join(
            [
                f"Fecha: {immediate_action.effectiveness_verified_at.isoformat()}",
                f"Resultado: {'Eficaz' if is_effective else 'No eficaz'}",
                f"Observacion: {check_comment}",
            ]
        ),
        actor=user,
        changed_at=now,
    )
    record_audit_event(
        entity=locked,
        action="anomaly.observation_effectiveness_verified",
        actor=user,
        before_data=before,
        after_data=snapshot_anomaly(locked) | {"immediate_action_id": str(immediate_action.pk)},
        request_id=_request_id(request_id),
    )
    complete_observation_effectiveness_assignment(
        anomaly=locked,
        actor=user,
        request_id=request_id,
    )
    return immediate_action


@transaction.atomic
def save_immediate_action(*, anomaly: Anomaly, user, data: dict, request_id: str = "") -> AnomalyImmediateAction:
    immediate_action = save_observation_load(anomaly=anomaly, user=user, data=data, request_id=request_id)
    if (data.get("actions_taken") or "").strip():
        data = {
            **data,
            "action_completed_at": data.get("action_completed_at") or data.get("action_date"),
            "effectiveness_due_at": data.get("effectiveness_due_at") or data.get("action_date"),
        }
        immediate_action = save_observation_action_taken(anomaly=anomaly, user=user, data=data, request_id=request_id)
    if data.get("effectiveness_is_effective") is not None:
        immediate_action = verify_observation_effectiveness(anomaly=anomaly, user=user, data=data, request_id=request_id)
    return immediate_action
def transition_anomaly(*, anomaly: Anomaly, user, target_stage: str | None = None, target_status: str | None = None, comment: str, request_id: str = "") -> Anomaly:
    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    _ensure_anomaly_is_editable(locked)
    _ensure_scope(locked.site_id, locked.area_id, user)

    if target_status == AnomalyStatus.CANCELLED:
        target_stage = target_stage or locked.current_stage
    elif not target_stage:
        raise ValidationError({"target_stage": "Debe indicar la etapa destino."})

    reopened = target_status == AnomalyStatus.REOPENED
    resolved_target_status = target_status or resolve_status_for_stage(target_stage, reopened=reopened)

    ensure_transition_permission(
        anomaly=locked,
        user=user,
        target_status=resolved_target_status,
        target_stage=target_stage,
    )
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














