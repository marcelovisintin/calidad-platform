from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import PERMISSION_ANALYZE_ANOMALY, PERMISSION_ASSIGN_ACTION
from apps.accounts.models import User
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentEffectivenessValidationResult,
    TreatmentEvidence,
    TreatmentLearnedLesson,
    TreatmentLearnedLessonEvidence,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskEvidence,
)
from apps.audit.services import record_audit_event
from apps.anomalies.models import (
    Anomaly,
    AnomalyCauseAnalysis,
    AnomalyStage,
    AnomalyStatus,
    AnomalyStatusHistory,
    ObservationResolutionPath,
)
from apps.anomalies.services.classification_rules import is_immediate_action_anomaly
from common.upload_validation import normalized_upload_content_type, validate_evidence_file


ALLOWED_TREATMENT_TRANSITIONS = {
    TreatmentStatus.PENDING: {TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS, TreatmentStatus.CANCELLED},
    TreatmentStatus.SCHEDULED: {TreatmentStatus.IN_PROGRESS, TreatmentStatus.CANCELLED},
    TreatmentStatus.IN_PROGRESS: {TreatmentStatus.COMPLETED, TreatmentStatus.CANCELLED},
    TreatmentStatus.COMPLETED: set(),
    TreatmentStatus.CANCELLED: set(),
}
OPEN_TREATMENT_STATUSES = {TreatmentStatus.PENDING, TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS}

def _request_id(value: str | None) -> str:
    return (value or "").strip()



def _require_treatment_permission(user, message: str, treatment: Treatment | None = None) -> None:
    if user.is_superuser:
        return
    access_level = getattr(user, "access_level", "")
    if access_level in {
        User.AccessLevel.ADMINISTRADOR,
        User.AccessLevel.DESARROLLADOR,
        User.AccessLevel.MANDO_MEDIO_ACTIVO,
    }:
        return
    if user.has_perm(PERMISSION_ASSIGN_ACTION) or user.has_perm(PERMISSION_ANALYZE_ANOMALY):
        return
    if treatment is not None:
        if treatment.created_by_id == user.id:
            return
        if getattr(treatment, "primary_anomaly_id", None) and getattr(getattr(treatment, "primary_anomaly", None), "reporter_id", None) == user.id:
            return
        if treatment.participants.filter(user_id=user.id).exists():
            return
        if treatment.tasks.filter(responsible_id=user.id).exists():
            return
    raise PermissionDenied(message)



def _bump_version(instance) -> None:
    instance.row_version = (instance.row_version or 0) + 1



def _next_treatment_code() -> str:
    year = timezone.localdate().year
    prefix = f"TRT-{year}-"
    last = (
        Treatment.objects.filter(code__startswith=prefix)
        .order_by("-code")
        .values_list("code", flat=True)
        .first()
    )
    sequence = 1
    if last:
        try:
            sequence = int(last.split("-")[-1]) + 1
        except (TypeError, ValueError):
            sequence = Treatment.objects.filter(code__startswith=prefix).count() + 1

    while True:
        code = f"{prefix}{sequence:04d}"
        if not Treatment.objects.filter(code=code).exists():
            return code
        sequence += 1



def _next_root_cause_sequence(treatment: Treatment) -> int:
    return (treatment.root_causes.aggregate(max_seq=models.Max("sequence")).get("max_seq") or 0) + 1



def _next_task_code(treatment: Treatment) -> str:
    seq = treatment.tasks.count() + 1
    return f"{treatment.code}-T{seq:02d}"




def snapshot_treatment(treatment: Treatment) -> dict:
    return {
        "id": str(treatment.pk),
        "code": treatment.code,
        "primary_anomaly_id": str(treatment.primary_anomaly_id),
        "status": treatment.status,
        "scheduled_for": treatment.scheduled_for.isoformat() if treatment.scheduled_for else "",
        "treatment_location": treatment.treatment_location,
        "method_used": treatment.method_used,
        "observations": treatment.observations,
        "effectiveness_evaluation_date": treatment.effectiveness_evaluation_date.isoformat() if treatment.effectiveness_evaluation_date else "",
        "effectiveness_responsible_id": str(treatment.effectiveness_responsible_id or ""),
        "effectiveness_validation_result": treatment.effectiveness_validation_result,
        "effectiveness_validated_at": treatment.effectiveness_validated_at.isoformat() if treatment.effectiveness_validated_at else "",
        "effectiveness_validated_by_id": str(treatment.effectiveness_validated_by_id or ""),
        "effectiveness_validation_comment": treatment.effectiveness_validation_comment,
    }


def _validate_effectiveness_assignment(*, treatment: Treatment, data: dict) -> None:
    evaluation_date = data.get("effectiveness_evaluation_date", treatment.effectiveness_evaluation_date)
    responsible = data.get("effectiveness_responsible", treatment.effectiveness_responsible)

    if not evaluation_date:
        raise ValidationError({"effectiveness_evaluation_date": "Debe indicar la fecha de evaluacion de eficacia."})
    if not responsible:
        raise ValidationError({"effectiveness_responsible": "Debe seleccionar el responsable de evaluacion de eficacia."})
    if not treatment.participants.filter(user_id=responsible.pk).exists():
        raise ValidationError(
            {"effectiveness_responsible": "El responsable de evaluacion de eficacia debe estar convocado al tratamiento."}
        )


def _validate_treatment_task_responsible(*, treatment: Treatment, responsible) -> None:
    if responsible and not treatment.participants.filter(user_id=responsible.pk).exists():
        raise ValidationError({"responsible": "El responsable de la tarea debe estar convocado al tratamiento."})


def is_treatment_closed_by_effective_validation(treatment: Treatment) -> bool:
    return bool(
        treatment.status == TreatmentStatus.COMPLETED
        and treatment.effectiveness_validation_result == TreatmentEffectivenessValidationResult.EFFECTIVE
    )


def is_open_treatment_for_association(treatment: Treatment) -> bool:
    return treatment.status in OPEN_TREATMENT_STATUSES and not treatment.effectiveness_validation_result


def ensure_anomaly_available_for_treatment(anomaly, field: str = "anomaly") -> None:
    if anomaly.current_status in {AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED}:
        raise ValidationError({field: "La anomalia esta cerrada o anulada y no puede vincularse a tratamiento."})
    if is_immediate_action_anomaly(anomaly) and anomaly.observation_resolution_path:
        if anomaly.observation_resolution_path == ObservationResolutionPath.OBSERVATION:
            raise ValidationError({field: "La anomalia ya fue tomada por Observacion y no puede vincularse a tratamiento."})
        raise ValidationError({field: "La anomalia ya fue derivada a Tratamiento."})
    if anomaly.severity_id is None:
        raise ValidationError({field: "La anomalia no tiene Revisión de hallazgos clasificada para tratamiento."})
    if not hasattr(anomaly, "initial_verification"):
        raise ValidationError({field: "La anomalia no tiene verificacion inicial registrada."})
    classification = getattr(anomaly, "classification", None)
    if not classification or not classification.requires_action_plan:
        raise ValidationError({field: "La anomalia no esta clasificada para tratamiento."})


def _mark_observation_path_for_treatment(*, anomaly, user, treatment_code: str | None = None) -> None:
    locked = Anomaly.objects.select_for_update().get(pk=anomaly.pk)
    ensure_anomaly_available_for_treatment(locked)

    if not is_immediate_action_anomaly(locked):
        return

    previous_path = locked.observation_resolution_path
    now = timezone.now()
    locked.observation_resolution_path = ObservationResolutionPath.TREATMENT
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save(update_fields=["observation_resolution_path", "updated_by", "row_version", "updated_at"])

    treatment_label = f" {treatment_code}" if treatment_code else ""
    _register_anomaly_history_event(
        anomaly=locked,
        user=user,
        comment=f"Camino elegido: TREATMENT. La Observacion se deriva a Tratamiento{treatment_label}.",
        evidence_note=f"Camino anterior: {previous_path or 'sin definir'}\nCamino nuevo: {ObservationResolutionPath.TREATMENT}",
        changed_at=now,
    )
    record_audit_event(
        entity=locked,
        action="anomaly.observation_path_selected",
        actor=user,
        before_data={"observation_resolution_path": previous_path or ""},
        after_data={"observation_resolution_path": ObservationResolutionPath.TREATMENT},
    )


def ensure_treatment_is_editable(treatment: Treatment) -> None:
    if is_treatment_closed_by_effective_validation(treatment):
        raise ValidationError(
            {"treatment": "El tratamiento esta cerrado por validacion eficaz y no admite modificaciones."}
        )


def _effectiveness_history_comment(treatment: Treatment) -> str:
    evaluation_date = treatment.effectiveness_evaluation_date.isoformat() if treatment.effectiveness_evaluation_date else "sin fecha"
    responsible = treatment.effectiveness_responsible
    responsible_name = responsible.full_name if responsible else "sin responsable"
    return (
        f"Tratamiento {treatment.code}: se registra la evaluacion de eficacia "
        f"para fecha {evaluation_date}, responsable {responsible_name}."
    )


def get_treatment_validation_state(treatment: Treatment) -> dict:
    blockers: list[str] = []

    if not treatment.scheduled_for:
        blockers.append("Debe tener fecha de tratamiento agendada.")
    elif treatment.scheduled_for > timezone.now():
        blockers.append("La fecha de tratamiento agendada aun no paso.")

    root_causes = list(treatment.root_causes.all())
    if not root_causes:
        blockers.append("Debe tener al menos una causa raiz cargada.")
    elif any(not (cause.description or "").strip() for cause in root_causes):
        blockers.append("Todas las causas raiz deben tener detalle.")

    if not treatment.effectiveness_evaluation_date or not treatment.effectiveness_responsible_id:
        blockers.append("Debe tener cargada la evaluacion de eficacia con fecha y responsable.")

    incomplete_tasks = [
        task.code or task.title
        for task in treatment.tasks.all()
        if task.status != "completed"
    ]
    if incomplete_tasks:
        blockers.append("Todas las tareas surgidas del tratamiento deben estar completadas.")

    return {"available": not blockers, "blockers": blockers}


def snapshot_learned_lesson(lesson: TreatmentLearnedLesson) -> dict:
    return {
        "id": str(lesson.pk),
        "treatment_id": str(lesson.treatment_id),
        "has_learning": lesson.has_learning,
        "learned_text": lesson.learned_text,
        "no_learning_reason": lesson.no_learning_reason,
        "procedure_modified": lesson.procedure_modified,
        "procedure_modification_notes": lesson.procedure_modification_notes,
        "saved_by_id": str(lesson.saved_by_id or ""),
        "saved_at": lesson.saved_at.isoformat() if lesson.saved_at else "",
    }


@transaction.atomic
def save_treatment_learned_lesson(*, treatment: Treatment, user, data: dict, files=None, request_id: str = "") -> TreatmentLearnedLesson:
    _require_treatment_permission(user, "No tiene permisos para registrar lecciones aprendidas.", treatment=treatment)
    locked = Treatment.objects.select_for_update().get(pk=treatment.pk)
    if locked.effectiveness_validation_result != TreatmentEffectivenessValidationResult.EFFECTIVE:
        raise ValidationError({"treatment": "Solo se pueden registrar lecciones aprendidas en tratamientos validados como eficaces."})

    lesson = TreatmentLearnedLesson.objects.select_for_update().filter(treatment=locked).first()
    before = snapshot_learned_lesson(lesson) if lesson else {}
    if not lesson:
        lesson = TreatmentLearnedLesson(treatment=locked, created_by=user)

    lesson.has_learning = data["has_learning"]
    lesson.learned_text = data.get("learned_text", "")
    lesson.no_learning_reason = data.get("no_learning_reason", "")
    lesson.procedure_modified = data["procedure_modified"]
    lesson.procedure_modification_notes = data.get("procedure_modification_notes", "")
    lesson.saved_by = user
    lesson.saved_at = timezone.now()
    lesson.updated_by = user
    _bump_version(lesson)
    lesson.full_clean()
    lesson.save()

    for file_obj in files or []:
        validate_evidence_file(file_obj)
        TreatmentLearnedLessonEvidence.objects.create(
            learned_lesson=lesson,
            file=file_obj,
            original_name=getattr(file_obj, "name", "") or "evidencia",
            content_type=normalized_upload_content_type(file_obj),
            uploaded_by=user,
            created_by=user,
            updated_by=user,
        )

    record_audit_event(
        entity=locked,
        action="treatment.learned_lesson.saved",
        actor=user,
        before_data=before,
        after_data=snapshot_learned_lesson(lesson),
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=locked,
        user=user,
        comment=f"Tratamiento {locked.code}: se registra o actualiza la leccion aprendida.",
    )
    return lesson


def _validation_history_comment(*, treatment: Treatment, previous_status: str, result: str, comment: str = "") -> str:
    result_label = "eficaz" if result == TreatmentEffectivenessValidationResult.EFFECTIVE else "no eficaz"
    new_status = treatment.status
    base = (
        f"Tratamiento {treatment.code}: validacion de eficacia realizada con resultado {result_label}. "
        f"El tratamiento cambia de estado {previous_status} a estado {new_status}."
    )
    clean_comment = (comment or "").strip()
    if clean_comment:
        return f"{base} Observacion: {clean_comment}"
    return base


def _register_anomaly_history_event(*, anomaly, user, comment: str, changed_at=None, evidence_note: str = "") -> None:
    AnomalyStatusHistory.objects.create(
        anomaly=anomaly,
        from_status=anomaly.current_status,
        to_status=anomaly.current_status,
        from_stage=anomaly.current_stage,
        to_stage=anomaly.current_stage,
        comment=comment,
        evidence_note=(evidence_note or "").strip(),
        changed_by=user,
        changed_at=changed_at or timezone.now(),
        created_by=user,
        updated_by=user,
    )


def _register_history_for_treatment(*, treatment: Treatment, user, comment: str, evidence_note: str = "") -> None:
    links = TreatmentAnomaly.objects.filter(treatment=treatment).select_related("anomaly")
    anomalies_by_id = {link.anomaly_id: link.anomaly for link in links}
    if treatment.primary_anomaly_id and treatment.primary_anomaly_id not in anomalies_by_id:
        anomalies_by_id[treatment.primary_anomaly_id] = treatment.primary_anomaly

    for anomaly in anomalies_by_id.values():
        _register_anomaly_history_event(
            anomaly=anomaly,
            user=user,
            comment=comment,
            evidence_note=evidence_note,
        )


def _close_anomalies_for_effective_treatment(*, treatment: Treatment, user, changed_at) -> None:
    links = TreatmentAnomaly.objects.filter(treatment=treatment).select_related("anomaly")
    anomalies_by_id = {link.anomaly_id: link.anomaly for link in links}
    if treatment.primary_anomaly_id and treatment.primary_anomaly_id not in anomalies_by_id:
        anomalies_by_id[treatment.primary_anomaly_id] = treatment.primary_anomaly

    comment = (
        "Tratamiento validado como eficaz. "
        "Anomalia cerrada automaticamente por cierre efectivo del tratamiento."
    )
    for anomaly in anomalies_by_id.values():
        if anomaly.current_status == AnomalyStatus.CLOSED:
            _register_anomaly_history_event(
                anomaly=anomaly,
                user=user,
                comment=comment,
                changed_at=changed_at,
            )
            continue

        previous_status = anomaly.current_status
        previous_stage = anomaly.current_stage
        anomaly.current_status = AnomalyStatus.CLOSED
        anomaly.current_stage = AnomalyStage.CLOSURE
        anomaly.closed_at = changed_at
        anomaly.last_transition_at = changed_at
        anomaly.effectiveness_summary = "Tratamiento validado como eficaz."
        anomaly.closure_comment = comment
        anomaly.updated_by = user
        _bump_version(anomaly)
        anomaly.full_clean()
        anomaly.save(
            update_fields=[
                "current_status",
                "current_stage",
                "closed_at",
                "last_transition_at",
                "effectiveness_summary",
                "closure_comment",
                "updated_by",
                "row_version",
                "updated_at",
            ]
        )
        AnomalyStatusHistory.objects.create(
            anomaly=anomaly,
            from_status=previous_status,
            to_status=anomaly.current_status,
            from_stage=previous_stage,
            to_stage=anomaly.current_stage,
            comment=comment,
            changed_by=user,
            changed_at=changed_at,
            created_by=user,
            updated_by=user,
        )


def _sync_treatment_analysis_to_anomalies(*, treatment: Treatment, user) -> None:
    method_used = (treatment.method_used or "").strip()
    observations = (treatment.observations or "").strip()
    if not method_used and not observations:
        return

    method_value = method_used or "other"
    summary_value = observations or f"Analisis registrado desde tratamiento {treatment.code}."
    now = timezone.now()

    links = TreatmentAnomaly.objects.filter(treatment=treatment).select_related("anomaly")
    for link in links:
        anomaly = link.anomaly
        analysis, created = AnomalyCauseAnalysis.objects.get_or_create(
            anomaly=anomaly,
            defaults={
                "analyzed_by": user,
                "analyzed_at": now,
                "method_used": method_value,
                "immediate_cause": observations,
                "root_cause": summary_value,
                "summary": summary_value,
                "created_by": user,
                "updated_by": user,
            },
        )

        if not created:
            analysis.analyzed_by = user
            analysis.analyzed_at = now
            if method_used:
                analysis.method_used = method_value
            if observations:
                analysis.immediate_cause = observations
                analysis.summary = summary_value
                if not (analysis.root_cause or "").strip():
                    analysis.root_cause = summary_value
            elif not (analysis.summary or "").strip():
                analysis.summary = summary_value
            analysis.updated_by = user
            analysis.full_clean()
            analysis.save()

        anomaly.root_cause_summary = analysis.root_cause or analysis.summary or anomaly.root_cause_summary
        anomaly.updated_by = user
        _bump_version(anomaly)
        anomaly.save(update_fields=["root_cause_summary", "updated_by", "row_version", "updated_at"])



def _transition_anomaly_stage(*, anomaly, user, target_stage: str, target_status: str, comment: str) -> None:
    if anomaly.current_status in {AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED}:
        return

    if anomaly.current_status not in {
        AnomalyStatus.REGISTERED,
        AnomalyStatus.IN_EVALUATION,
        AnomalyStatus.IN_ANALYSIS,
        AnomalyStatus.REOPENED,
    }:
        _register_anomaly_history_event(anomaly=anomaly, user=user, comment=comment)
        return

    if anomaly.current_stage == target_stage and anomaly.current_status == target_status:
        _register_anomaly_history_event(anomaly=anomaly, user=user, comment=comment)
        return

    previous_status = anomaly.current_status
    previous_stage = anomaly.current_stage
    now = timezone.now()

    anomaly.current_stage = target_stage
    anomaly.current_status = target_status
    anomaly.last_transition_at = now
    anomaly.updated_by = user
    _bump_version(anomaly)
    anomaly.save(
        update_fields=[
            "current_stage",
            "current_status",
            "last_transition_at",
            "updated_by",
            "row_version",
            "updated_at",
        ]
    )

    AnomalyStatusHistory.objects.create(
        anomaly=anomaly,
        from_status=previous_status,
        to_status=target_status,
        from_stage=previous_stage,
        to_stage=target_stage,
        comment=comment,
        changed_by=user,
        changed_at=now,
        created_by=user,
        updated_by=user,
    )



def _move_anomaly_to_treatment_created(*, anomaly, user, comment: str) -> None:
    allowed_stages = {
        AnomalyStage.REGISTRATION,
        AnomalyStage.CONTAINMENT,
        AnomalyStage.INITIAL_VERIFICATION,
        AnomalyStage.CLASSIFICATION,
        AnomalyStage.TREATMENT_CREATED,
    }
    if anomaly.current_stage not in allowed_stages:
        _register_anomaly_history_event(anomaly=anomaly, user=user, comment=comment)
        return

    _transition_anomaly_stage(
        anomaly=anomaly,
        user=user,
        target_stage=AnomalyStage.TREATMENT_CREATED,
        target_status=AnomalyStatus.IN_ANALYSIS,
        comment=comment,
    )



def _move_anomaly_to_cause_analysis(*, anomaly, user, comment: str) -> None:
    _transition_anomaly_stage(
        anomaly=anomaly,
        user=user,
        target_stage=AnomalyStage.CAUSE_ANALYSIS,
        target_status=AnomalyStatus.IN_ANALYSIS,
        comment=comment,
    )



def _ensure_treatment_in_progress(*, treatment: Treatment, user, reason: str) -> bool:
    if treatment.status not in {TreatmentStatus.PENDING, TreatmentStatus.SCHEDULED}:
        return False

    treatment.status = TreatmentStatus.IN_PROGRESS
    treatment.updated_by = user
    _bump_version(treatment)
    treatment.full_clean()
    treatment.save(update_fields=["status", "updated_by", "row_version", "updated_at"])

    _register_history_for_treatment(
        treatment=treatment,
        user=user,
        comment=reason,
    )
    return True


@transaction.atomic
def create_treatment(*, primary_anomaly, user, data: dict, request_id: str = "") -> Treatment:
    _require_treatment_permission(user, "No tiene permisos para crear tratamientos.")

    ensure_anomaly_available_for_treatment(primary_anomaly, field="primary_anomaly")

    if Treatment.objects.filter(primary_anomaly=primary_anomaly).exists():
        raise ValidationError({"primary_anomaly": "La anomalia ya tiene un tratamiento principal asociado."})

    treatment = Treatment(
        code=_next_treatment_code(),
        primary_anomaly=primary_anomaly,
        status=data.get("status") or TreatmentStatus.PENDING,
        scheduled_for=data.get("scheduled_for"),
        treatment_location=(data.get("treatment_location") or "").strip(),
        method_used=data.get("method_used", ""),
        observations=data.get("observations", ""),
        created_by=user,
        updated_by=user,
    )
    treatment.full_clean()
    treatment.save()

    _mark_observation_path_for_treatment(
        anomaly=primary_anomaly,
        user=user,
        treatment_code=treatment.code,
    )

    TreatmentAnomaly.objects.create(
        treatment=treatment,
        anomaly=primary_anomaly,
        is_primary=True,
        created_by=user,
        updated_by=user,
    )

    links = TreatmentAnomaly.objects.filter(treatment=treatment).select_related("anomaly")
    for link in links:
        _move_anomaly_to_treatment_created(
            anomaly=link.anomaly,
            user=user,
            comment=f"Tratamiento {treatment.code}: se crea el tratamiento y la anomalia pasa a tratamiento creado.",
        )

    record_audit_event(
        entity=treatment,
        action="treatment.created",
        actor=user,
        after_data=snapshot_treatment(treatment),
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=treatment,
        user=user,
        comment=f"Se crea el tratamiento {treatment.code} para la anomalia.",
    )
    return treatment



@transaction.atomic
def update_treatment(*, treatment: Treatment, user, data: dict, request_id: str = "") -> Treatment:
    _require_treatment_permission(user, "No tiene permisos para actualizar tratamientos.", treatment=treatment)
    locked = Treatment.objects.select_for_update().get(pk=treatment.pk)
    ensure_treatment_is_editable(locked)
    before = snapshot_treatment(locked)

    status_changed = False
    auto_progressed = False
    if "status" in data and data["status"] != locked.status:
        target = data["status"]
        allowed = ALLOWED_TREATMENT_TRANSITIONS.get(locked.status, set())
        if target not in allowed:
            raise ValidationError({"status": "La transicion de estado del tratamiento no es valida."})
        locked.status = target
        status_changed = True

    if (
        "effectiveness_evaluation_date" in data
        or "effectiveness_responsible" in data
        or data.get("status") == TreatmentStatus.COMPLETED
    ):
        _validate_effectiveness_assignment(treatment=locked, data=data)

    if "treatment_location" in data:
        data["treatment_location"] = (data.get("treatment_location") or "").strip()

    for field in ("scheduled_for", "treatment_location", "method_used", "observations", "effectiveness_evaluation_date", "effectiveness_responsible"):
        if field in data:
            setattr(locked, field, data[field])

    analysis_updated = (
        ("method_used" in data and bool((data.get("method_used") or "").strip()))
        or ("observations" in data and bool((data.get("observations") or "").strip()))
    )

    if analysis_updated and "status" not in data and locked.status in {TreatmentStatus.PENDING, TreatmentStatus.SCHEDULED}:
        locked.status = TreatmentStatus.IN_PROGRESS
        auto_progressed = True

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    if analysis_updated:
        _sync_treatment_analysis_to_anomalies(treatment=locked, user=user)
        links = TreatmentAnomaly.objects.filter(treatment=locked).select_related("anomaly")
        for link in links:
            _move_anomaly_to_cause_analysis(
                anomaly=link.anomaly,
                user=user,
                comment=f"Tratamiento {locked.code}: analisis de causa en curso.",
            )

    record_audit_event(
        entity=locked,
        action="treatment.updated",
        actor=user,
        before_data=before,
        after_data=snapshot_treatment(locked),
        request_id=_request_id(request_id),
    )

    comments: list[str] = []
    if status_changed or auto_progressed:
        comments.append(f"El tratamiento {locked.code} cambia a estado {locked.status}.")
    if "scheduled_for" in data or "treatment_location" in data:
        comments.append("Se actualiza la agenda del tratamiento.")
    if "effectiveness_evaluation_date" in data or "effectiveness_responsible" in data:
        comments.append(_effectiveness_history_comment(locked))
    if analysis_updated:
        comments.append("Se guarda el analisis de causa del tratamiento.")

    if comments:
        _register_history_for_treatment(treatment=locked, user=user, comment=" ".join(comments))

    return locked


@transaction.atomic
def validate_treatment_effectiveness(*, treatment: Treatment, user, result: str, comment: str = "", request_id: str = "") -> Treatment:
    _require_treatment_permission(user, "No tiene permisos para validar tratamientos.", treatment=treatment)
    locked = (
        Treatment.objects.select_for_update(of=("self",))
        .select_related("effectiveness_responsible")
        .prefetch_related("root_causes", "tasks", "anomaly_links__anomaly")
        .get(pk=treatment.pk)
    )
    ensure_treatment_is_editable(locked)
    before = snapshot_treatment(locked)

    if not locked.effectiveness_responsible_id:
        raise ValidationError({"effectiveness_responsible": "El tratamiento no tiene responsable de evaluacion de eficacia."})
    if locked.effectiveness_responsible_id != user.pk:
        raise PermissionDenied("Solo el responsable designado puede validar la eficacia del tratamiento.")

    validation_state = get_treatment_validation_state(locked)
    if not validation_state["available"]:
        raise ValidationError({"validation": validation_state["blockers"]})

    previous_status = locked.status
    now = timezone.now()
    if result == TreatmentEffectivenessValidationResult.EFFECTIVE:
        locked.status = TreatmentStatus.COMPLETED
    elif result == TreatmentEffectivenessValidationResult.NOT_EFFECTIVE:
        locked.status = TreatmentStatus.IN_PROGRESS
    else:
        raise ValidationError({"result": "Resultado de validacion invalido."})

    locked.effectiveness_validation_result = result
    locked.effectiveness_validated_at = now
    locked.effectiveness_validated_by = user
    locked.effectiveness_validation_comment = (comment or "").strip()
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    record_audit_event(
        entity=locked,
        action="treatment.effectiveness_validated",
        actor=user,
        before_data=before,
        after_data=snapshot_treatment(locked),
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=locked,
        user=user,
        comment=_validation_history_comment(
            treatment=locked,
            previous_status=previous_status,
            result=result,
            comment=comment,
        ),
    )
    if result == TreatmentEffectivenessValidationResult.EFFECTIVE:
        _close_anomalies_for_effective_treatment(treatment=locked, user=user, changed_at=timezone.now())
    return locked


@transaction.atomic
def add_treatment_anomaly(*, treatment: Treatment, anomaly, user, request_id: str = "") -> TreatmentAnomaly:
    _require_treatment_permission(user, "No tiene permisos para asociar anomalias al tratamiento.", treatment=treatment)
    ensure_treatment_is_editable(treatment)
    if not is_open_treatment_for_association(treatment):
        raise ValidationError({"treatment": "Solo se pueden asociar anomalias a tratamientos abiertos y no validados."})
    ensure_anomaly_available_for_treatment(anomaly)
    _mark_observation_path_for_treatment(
        anomaly=anomaly,
        user=user,
        treatment_code=treatment.code,
    )
    link, created = TreatmentAnomaly.objects.get_or_create(
        treatment=treatment,
        anomaly=anomaly,
        defaults={"created_by": user, "updated_by": user},
    )
    if not created:
        raise ValidationError({"anomaly": "La anomalia ya esta asociada a este tratamiento."})

    record_audit_event(
        entity=treatment,
        action="treatment.anomaly_added",
        actor=user,
        after_data={"anomaly_id": str(anomaly.pk)},
        request_id=_request_id(request_id),
    )
    _register_anomaly_history_event(
        anomaly=anomaly,
        user=user,
        comment=f"La anomalia se vincula al tratamiento {treatment.code}.",
    )
    return link



@transaction.atomic
def add_treatment_participant(*, treatment: Treatment, participant_user, role: str, note: str, user, request_id: str = "") -> TreatmentParticipant:
    _require_treatment_permission(user, "No tiene permisos para convocar participantes al tratamiento.", treatment=treatment)
    ensure_treatment_is_editable(treatment)
    participant, created = TreatmentParticipant.objects.get_or_create(
        treatment=treatment,
        user=participant_user,
        defaults={"role": role, "note": note, "created_by": user, "updated_by": user},
    )
    if not created:
        participant.role = role
        participant.note = note
        participant.updated_by = user
        participant.full_clean()
        participant.save()

    record_audit_event(
        entity=treatment,
        action="treatment.participant_added" if created else "treatment.participant_updated",
        actor=user,
        after_data={"user_id": str(participant_user.pk), "role": role},
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=treatment,
        user=user,
        comment=(
            f"Se convoca al usuario {participant_user.username} en el tratamiento {treatment.code}."
            if created
            else f"Se actualiza la convocatoria de {participant_user.username} en el tratamiento {treatment.code}."
        ),
    )
    return participant



@transaction.atomic
def add_root_cause(*, treatment: Treatment, description: str, user, request_id: str = "") -> TreatmentRootCause:
    _require_treatment_permission(user, "No tiene permisos para registrar causas raiz.", treatment=treatment)
    ensure_treatment_is_editable(treatment)
    if not description.strip():
        raise ValidationError({"description": "La descripcion de la causa raiz es obligatoria."})

    locked_treatment = Treatment.objects.select_for_update().get(pk=treatment.pk)
    sequence = (locked_treatment.root_causes.aggregate(max_seq=models.Max("sequence")).get("max_seq") or 0) + 1
    root_cause = TreatmentRootCause.objects.create(
        treatment=locked_treatment,
        sequence=sequence,
        description=description.strip(),
        created_by=user,
        updated_by=user,
    )

    _ensure_treatment_in_progress(
        treatment=locked_treatment,
        user=user,
        reason=f"Tratamiento {locked_treatment.code}: pasa a en curso por inicio de analisis de causa.",
    )

    links = TreatmentAnomaly.objects.filter(treatment=locked_treatment).select_related("anomaly")
    for link in links:
        _move_anomaly_to_cause_analysis(
            anomaly=link.anomaly,
            user=user,
            comment=f"Tratamiento {locked_treatment.code}: se inicia analisis de causa.",
        )

    record_audit_event(
        entity=locked_treatment,
        action="treatment.root_cause_added",
        actor=user,
        after_data={"root_cause_id": str(root_cause.pk), "sequence": sequence},
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=locked_treatment,
        user=user,
        comment=f"Tratamiento {locked_treatment.code}: se registra la causa raiz {sequence}.",
    )
    return root_cause


@transaction.atomic
def add_treatment_task(*, treatment: Treatment, data: dict, user, request_id: str = "") -> TreatmentTask:
    _require_treatment_permission(user, "No tiene permisos para registrar tareas de tratamiento.", treatment=treatment)
    ensure_treatment_is_editable(treatment)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError({"title": "El titulo de la tarea es obligatorio."})

    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError({"description": "La descripcion de la tarea es obligatoria."})

    root_causes = list(data.get("root_cause_ids") or [])
    if data.get("root_cause") and data["root_cause"] not in root_causes:
        root_causes.append(data["root_cause"])
    if not root_causes:
        raise ValidationError({"root_cause_ids": "Debe seleccionar al menos una causa raiz."})

    responsible = data.get("responsible")
    if not responsible:
        raise ValidationError({"responsible": "Debe seleccionar un responsable para la tarea."})
    _validate_treatment_task_responsible(treatment=treatment, responsible=responsible)

    execution_date = data.get("execution_date")
    if not execution_date:
        raise ValidationError({"execution_date": "Debe indicar la fecha de ejecucion."})

    anomaly_ids = data.get("anomaly_ids") or []
    if not anomaly_ids:
        raise ValidationError({"anomaly_ids": "Debe vincular al menos una anomalia a la tarea."})

    task = TreatmentTask(
        treatment=treatment,
        root_cause=root_causes[0],
        code=data.get("code") or _next_task_code(treatment),
        title=title,
        description=description,
        responsible=responsible,
        execution_date=execution_date,
        status=data.get("status") or "pending",
        created_by=user,
        updated_by=user,
    )
    task.full_clean()
    task.save()
    task.root_causes.set(root_causes)

    links = []
    for anomaly_id in anomaly_ids:
        links.append(
            TreatmentTaskAnomaly(
                task=task,
                anomaly_id=anomaly_id,
                created_by=user,
                updated_by=user,
            )
        )
    TreatmentTaskAnomaly.objects.bulk_create(links, ignore_conflicts=True)

    record_audit_event(
        entity=treatment,
        action="treatment.task_added",
        actor=user,
        after_data={"task_id": str(task.pk), "title": task.title},
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=treatment,
        user=user,
        comment=f"Tratamiento {treatment.code}: se crea la tarea {task.code or task.title}.",
    )
    return task



@transaction.atomic
def update_treatment_task(*, treatment_task: TreatmentTask, data: dict, user, request_id: str = "") -> TreatmentTask:
    _require_treatment_permission(user, "No tiene permisos para actualizar tareas de tratamiento.", treatment=treatment_task.treatment)
    ensure_treatment_is_editable(treatment_task.treatment)
    locked = TreatmentTask.objects.select_for_update().get(pk=treatment_task.pk)
    previous_status = locked.status
    next_status = data.get("status", locked.status)
    status_changed = "status" in data and next_status != previous_status
    evidence_note = (data.pop("evidence_note", "") or "").strip()

    if status_changed and not evidence_note:
        raise ValidationError({"evidence_note": "Debe cargar una nota de evidencia para cambiar el estado de la tarea."})

    root_causes = None
    if "root_cause_ids" in data or "root_cause" in data:
        root_causes = list(data.get("root_cause_ids") or [])
        if data.get("root_cause") and data["root_cause"] not in root_causes:
            root_causes.append(data["root_cause"])
        if not root_causes:
            raise ValidationError({"root_cause_ids": "Debe seleccionar al menos una causa raiz."})
        data["root_cause"] = root_causes[0]

    for field in ("title", "description", "responsible", "execution_date", "status", "root_cause"):
        if field in data:
            setattr(locked, field, data[field])

    if "responsible" in data:
        _validate_treatment_task_responsible(treatment=locked.treatment, responsible=locked.responsible)

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()
    if root_causes is not None:
        locked.root_causes.set(root_causes)

    if "anomaly_ids" in data:
        TreatmentTaskAnomaly.objects.filter(task=locked).delete()
        links = [
            TreatmentTaskAnomaly(
                task=locked,
                anomaly_id=anomaly_id,
                created_by=user,
                updated_by=user,
            )
            for anomaly_id in (data.get("anomaly_ids") or [])
        ]
        if links:
            TreatmentTaskAnomaly.objects.bulk_create(links, ignore_conflicts=True)

    record_audit_event(
        entity=locked.treatment,
        action="treatment.task_updated",
        actor=user,
        after_data={
            "task_id": str(locked.pk),
            "previous_status": previous_status,
            "status": locked.status,
            "evidence_note": evidence_note if status_changed else "",
        },
        request_id=_request_id(request_id),
    )
    if status_changed:
        _register_history_for_treatment(
            treatment=locked.treatment,
            user=user,
            comment=(
                f"Tratamiento {locked.treatment.code}: se actualiza la tarea "
                f"{locked.code or locked.title} de estado {previous_status} a estado {locked.status}."
            ),
            evidence_note=evidence_note,
        )
    else:
        _register_history_for_treatment(
            treatment=locked.treatment,
            user=user,
            comment=f"Tratamiento {locked.treatment.code}: se actualiza la tarea {locked.code or locked.title}.",
        )
    return locked


@transaction.atomic
def add_treatment_evidence(*, treatment: Treatment, user, data: dict, request_id: str = "") -> TreatmentEvidence:
    _require_treatment_permission(user, "No tiene permisos para agregar evidencias al tratamiento.", treatment=treatment)
    ensure_treatment_is_editable(treatment)

    file_obj = data.get("file")
    if not file_obj:
        raise ValidationError({"file": "Debe adjuntar un archivo de evidencia."})
    validate_evidence_file(file_obj)

    evidence = TreatmentEvidence(
        treatment=treatment,
        file=file_obj,
        original_name=data.get("original_name") or getattr(file_obj, "name", "evidencia"),
        content_type=normalized_upload_content_type(file_obj),
        note=(data.get("note") or "").strip(),
        uploaded_by=user,
        created_by=user,
        updated_by=user,
    )
    evidence.full_clean()
    evidence.save()

    record_audit_event(
        entity=treatment,
        action="treatment.evidence_added",
        actor=user,
        after_data={"evidence_id": str(evidence.pk), "original_name": evidence.original_name},
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=treatment,
        user=user,
        comment=f"Tratamiento {treatment.code}: se agrega evidencia objetiva ({evidence.original_name}).",
    )
    return evidence


@transaction.atomic
def add_treatment_task_evidence(*, treatment_task: TreatmentTask, user, data: dict, request_id: str = "") -> TreatmentTaskEvidence:
    treatment = treatment_task.treatment
    _require_treatment_permission(user, "No tiene permisos para agregar evidencias a la tarea.", treatment=treatment)
    ensure_treatment_is_editable(treatment)

    file_obj = data.get("file")
    if not file_obj:
        raise ValidationError({"file": "Debe adjuntar un archivo de evidencia."})
    validate_evidence_file(file_obj)

    evidence = TreatmentTaskEvidence(
        treatment_task=treatment_task,
        file=file_obj,
        original_name=data.get("original_name") or getattr(file_obj, "name", "evidencia"),
        content_type=normalized_upload_content_type(file_obj),
        note=(data.get("note") or "").strip(),
        uploaded_by=user,
        created_by=user,
        updated_by=user,
    )
    evidence.full_clean()
    evidence.save()

    _ensure_treatment_in_progress(
        treatment=treatment,
        user=user,
        reason=f"Tratamiento {treatment.code}: pasa a en curso por carga de evidencias en tareas.",
    )

    record_audit_event(
        entity=treatment,
        action="treatment.task_evidence_added",
        actor=user,
        after_data={
            "task_id": str(treatment_task.pk),
            "task_code": treatment_task.code,
            "evidence_id": str(evidence.pk),
            "original_name": evidence.original_name,
        },
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=treatment,
        user=user,
        comment=f"Tratamiento {treatment.code}: se agrega evidencia en tarea {treatment_task.code or treatment_task.title}.",
    )
    return evidence
