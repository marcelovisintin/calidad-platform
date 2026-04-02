from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.constants import PERMISSION_ANALYZE_ANOMALY, PERMISSION_ASSIGN_ACTION
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskAnomaly,
)
from apps.audit.services import record_audit_event


ALLOWED_TREATMENT_TRANSITIONS = {
    TreatmentStatus.PENDING: {TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS, TreatmentStatus.CANCELLED},
    TreatmentStatus.SCHEDULED: {TreatmentStatus.IN_PROGRESS, TreatmentStatus.CANCELLED},
    TreatmentStatus.IN_PROGRESS: {TreatmentStatus.COMPLETED, TreatmentStatus.CANCELLED},
    TreatmentStatus.COMPLETED: set(),
    TreatmentStatus.CANCELLED: set(),
}


def _request_id(value: str | None) -> str:
    return (value or "").strip()



def _require_treatment_permission(user, message: str) -> None:
    if user.is_superuser:
        return
    if user.has_perm(PERMISSION_ASSIGN_ACTION) or user.has_perm(PERMISSION_ANALYZE_ANOMALY):
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
        "method_used": treatment.method_used,
        "observations": treatment.observations,
    }



@transaction.atomic
def create_treatment(*, primary_anomaly, user, data: dict, request_id: str = "") -> Treatment:
    _require_treatment_permission(user, "No tiene permisos para crear tratamientos.")

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

    record_audit_event(
        entity=treatment,
        action="treatment.created",
        actor=user,
        after_data=snapshot_treatment(treatment),
        request_id=_request_id(request_id),
    )
    return treatment



@transaction.atomic
def update_treatment(*, treatment: Treatment, user, data: dict, request_id: str = "") -> Treatment:
    _require_treatment_permission(user, "No tiene permisos para actualizar tratamientos.")
    locked = Treatment.objects.select_for_update().get(pk=treatment.pk)
    before = snapshot_treatment(locked)

    if "status" in data and data["status"] != locked.status:
        target = data["status"]
        allowed = ALLOWED_TREATMENT_TRANSITIONS.get(locked.status, set())
        if target not in allowed:
            raise ValidationError({"status": "La transicion de estado del tratamiento no es valida."})
        locked.status = target

    for field in ("scheduled_for", "method_used", "observations"):
        if field in data:
            setattr(locked, field, data[field])

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    record_audit_event(
        entity=locked,
        action="treatment.updated",
        actor=user,
        before_data=before,
        after_data=snapshot_treatment(locked),
        request_id=_request_id(request_id),
    )
    return locked



@transaction.atomic
def add_treatment_anomaly(*, treatment: Treatment, anomaly, user, request_id: str = "") -> TreatmentAnomaly:
    _require_treatment_permission(user, "No tiene permisos para asociar anomalias al tratamiento.")
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
    return link



@transaction.atomic
def add_treatment_participant(*, treatment: Treatment, participant_user, role: str, note: str, user, request_id: str = "") -> TreatmentParticipant:
    _require_treatment_permission(user, "No tiene permisos para convocar participantes al tratamiento.")
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
    return participant



@transaction.atomic
def add_root_cause(*, treatment: Treatment, description: str, user, request_id: str = "") -> TreatmentRootCause:
    _require_treatment_permission(user, "No tiene permisos para registrar causas raiz.")
    if not description.strip():
        raise ValidationError({"description": "La descripcion de la causa raiz es obligatoria."})

    sequence = (treatment.root_causes.aggregate(max_seq=models.Max("sequence")).get("max_seq") or 0) + 1
    root_cause = TreatmentRootCause.objects.create(
        treatment=treatment,
        sequence=sequence,
        description=description.strip(),
        created_by=user,
        updated_by=user,
    )

    record_audit_event(
        entity=treatment,
        action="treatment.root_cause_added",
        actor=user,
        after_data={"root_cause_id": str(root_cause.pk), "sequence": sequence},
        request_id=_request_id(request_id),
    )
    return root_cause



@transaction.atomic
def add_treatment_task(*, treatment: Treatment, data: dict, user, request_id: str = "") -> TreatmentTask:
    _require_treatment_permission(user, "No tiene permisos para registrar tareas de tratamiento.")
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError({"title": "El titulo de la tarea es obligatorio."})

    task = TreatmentTask(
        treatment=treatment,
        root_cause=data.get("root_cause"),
        code=data.get("code") or _next_task_code(treatment),
        title=title,
        description=data.get("description", ""),
        responsible=data.get("responsible"),
        execution_date=data.get("execution_date"),
        status=data.get("status") or "pending",
        created_by=user,
        updated_by=user,
    )
    task.full_clean()
    task.save()

    anomaly_ids = data.get("anomaly_ids") or []
    if anomaly_ids:
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
    return task



@transaction.atomic
def update_treatment_task(*, treatment_task: TreatmentTask, data: dict, user, request_id: str = "") -> TreatmentTask:
    _require_treatment_permission(user, "No tiene permisos para actualizar tareas de tratamiento.")
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
    return locked

