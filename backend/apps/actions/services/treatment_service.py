from __future__ import annotations

from pathlib import Path

from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import PERMISSION_ANALYZE_ANOMALY, PERMISSION_ASSIGN_ACTION
from apps.accounts.models import User
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentEvidence,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskEvidence,
)
from apps.audit.services import record_audit_event
from apps.anomalies.models import AnomalyCauseAnalysis, AnomalyStage, AnomalyStatus, AnomalyStatusHistory
from apps.anomalies.services.classification_rules import is_immediate_action_anomaly


ALLOWED_TREATMENT_TRANSITIONS = {
    TreatmentStatus.PENDING: {TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS, TreatmentStatus.CANCELLED},
    TreatmentStatus.SCHEDULED: {TreatmentStatus.IN_PROGRESS, TreatmentStatus.CANCELLED},
    TreatmentStatus.IN_PROGRESS: {TreatmentStatus.COMPLETED, TreatmentStatus.CANCELLED},
    TreatmentStatus.COMPLETED: set(),
    TreatmentStatus.CANCELLED: set(),
}

ALLOWED_EVIDENCE_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/zip",
    "application/x-zip-compressed",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
}

ALLOWED_EVIDENCE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
    ".csv",
    ".rtf",
    ".odt",
    ".ods",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

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



def _validate_objective_file(file_obj) -> None:
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    file_name = (getattr(file_obj, "name", "") or "").lower()
    extension = Path(file_name).suffix

    if content_type in ALLOWED_EVIDENCE_CONTENT_TYPES:
        return
    if extension in ALLOWED_EVIDENCE_EXTENSIONS:
        return

    raise ValidationError({"file": "Solo se permiten evidencias en formato imagen, PDF, Word, Excel, texto o ZIP."})



def snapshot_treatment(treatment: Treatment) -> dict:
    return {
        "id": str(treatment.pk),
        "code": treatment.code,
        "primary_anomaly_id": str(treatment.primary_anomaly_id),
        "status": treatment.status,
        "scheduled_for": treatment.scheduled_for.isoformat() if treatment.scheduled_for else "",
        "method_used": treatment.method_used,
        "observations": treatment.observations,
    }


def _register_anomaly_history_event(*, anomaly, user, comment: str, changed_at=None) -> None:
    AnomalyStatusHistory.objects.create(
        anomaly=anomaly,
        from_status=anomaly.current_status,
        to_status=anomaly.current_status,
        from_stage=anomaly.current_stage,
        to_stage=anomaly.current_stage,
        comment=comment,
        changed_by=user,
        changed_at=changed_at or timezone.now(),
        created_by=user,
        updated_by=user,
    )


def _register_history_for_treatment(*, treatment: Treatment, user, comment: str) -> None:
    links = TreatmentAnomaly.objects.filter(treatment=treatment).select_related("anomaly")
    for link in links:
        _register_anomaly_history_event(anomaly=link.anomaly, user=user, comment=comment)


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

    if is_immediate_action_anomaly(primary_anomaly):
        raise ValidationError({"primary_anomaly": "Las anomalias con REVICION DE HALLAZGOS como accion inmediata no pueden crear tratamiento."})

    if Treatment.objects.filter(primary_anomaly=primary_anomaly).exists():
        raise ValidationError({"primary_anomaly": "La anomalia ya tiene un tratamiento principal asociado."})

    treatment = Treatment(
        code=_next_treatment_code(),
        primary_anomaly=primary_anomaly,
        status=data.get("status") or TreatmentStatus.PENDING,
        scheduled_for=data.get("scheduled_for"),
        method_used=data.get("method_used", ""),
        observations=data.get("observations", ""),
        created_by=user,
        updated_by=user,
    )
    treatment.full_clean()
    treatment.save()

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

    for field in ("scheduled_for", "method_used", "observations"):
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
    if "scheduled_for" in data:
        comments.append("Se actualiza la agenda del tratamiento.")
    if analysis_updated:
        comments.append("Se guarda el analisis de causa del tratamiento.")

    if comments:
        _register_history_for_treatment(treatment=locked, user=user, comment=" ".join(comments))

    return locked


@transaction.atomic
def add_treatment_anomaly(*, treatment: Treatment, anomaly, user, request_id: str = "") -> TreatmentAnomaly:
    _require_treatment_permission(user, "No tiene permisos para asociar anomalias al tratamiento.", treatment=treatment)
    if is_immediate_action_anomaly(anomaly):
        raise ValidationError({"anomaly": "Las anomalias con REVICION DE HALLAZGOS como accion inmediata no pueden vincularse a un tratamiento."})
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
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError({"title": "El titulo de la tarea es obligatorio."})

    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError({"description": "La descripcion de la tarea es obligatoria."})

    root_cause = data.get("root_cause")
    if not root_cause:
        raise ValidationError({"root_cause": "Debe seleccionar una causa raiz."})

    responsible = data.get("responsible")
    if not responsible:
        raise ValidationError({"responsible": "Debe seleccionar un responsable para la tarea."})

    execution_date = data.get("execution_date")
    if not execution_date:
        raise ValidationError({"execution_date": "Debe indicar la fecha de ejecucion."})

    anomaly_ids = data.get("anomaly_ids") or []
    if not anomaly_ids:
        raise ValidationError({"anomaly_ids": "Debe vincular al menos una anomalia a la tarea."})

    task = TreatmentTask(
        treatment=treatment,
        root_cause=root_cause,
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
    locked = TreatmentTask.objects.select_for_update().get(pk=treatment_task.pk)

    for field in ("title", "description", "responsible", "execution_date", "status", "root_cause"):
        if field in data:
            setattr(locked, field, data[field])

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

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
        after_data={"task_id": str(locked.pk), "status": locked.status},
        request_id=_request_id(request_id),
    )
    _register_history_for_treatment(
        treatment=locked.treatment,
        user=user,
        comment=f"Tratamiento {locked.treatment.code}: se actualiza la tarea {locked.code or locked.title} a estado {locked.status}.",
    )
    return locked


@transaction.atomic
def add_treatment_evidence(*, treatment: Treatment, user, data: dict, request_id: str = "") -> TreatmentEvidence:
    _require_treatment_permission(user, "No tiene permisos para agregar evidencias al tratamiento.", treatment=treatment)

    file_obj = data.get("file")
    if not file_obj:
        raise ValidationError({"file": "Debe adjuntar un archivo de evidencia."})
    _validate_objective_file(file_obj)

    evidence = TreatmentEvidence(
        treatment=treatment,
        file=file_obj,
        original_name=data.get("original_name") or getattr(file_obj, "name", "evidencia"),
        content_type=data.get("content_type") or getattr(file_obj, "content_type", ""),
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

    file_obj = data.get("file")
    if not file_obj:
        raise ValidationError({"file": "Debe adjuntar un archivo de evidencia."})
    _validate_objective_file(file_obj)

    evidence = TreatmentTaskEvidence(
        treatment_task=treatment_task,
        file=file_obj,
        original_name=data.get("original_name") or getattr(file_obj, "name", "evidencia"),
        content_type=data.get("content_type") or getattr(file_obj, "content_type", ""),
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
