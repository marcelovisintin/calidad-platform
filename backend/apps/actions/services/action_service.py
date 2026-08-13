from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.services.access_policy import (
    can_execute_assignment,
    has_global_access,
    is_management_user,
)
from apps.actions.models import (
    ActionEvidence,
    ActionHistoryEvent,
    ActionItem,
    ActionItemHistory,
    ActionItemStatus,
    ActionPlan,
    ActionPlanStatus,
)
from apps.audit.services import record_audit_event
from apps.notifications.services import (
    dismiss_action_assignment_tasks,
    notify_action_item_assigned,
    sync_action_assignment_task_status,
)
from common.upload_validation import validate_evidence_file

ALLOWED_ACTION_ITEM_TRANSITIONS = {
    ActionItemStatus.PENDING: {ActionItemStatus.IN_PROGRESS, ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED},
    ActionItemStatus.IN_PROGRESS: {ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED},
    ActionItemStatus.COMPLETED: set(),
    ActionItemStatus.CANCELLED: set(),
}

ALLOWED_ACTION_PLAN_TRANSITIONS = {
    ActionPlanStatus.DRAFT: {ActionPlanStatus.ACTIVE, ActionPlanStatus.CANCELLED},
    ActionPlanStatus.ACTIVE: {ActionPlanStatus.COMPLETED, ActionPlanStatus.CANCELLED},
    ActionPlanStatus.COMPLETED: set(),
    ActionPlanStatus.CANCELLED: set(),
}


def _request_id(value: str | None) -> str:
    return (value or "").strip()



def _can_manage_action_plan(user, action_plan: ActionPlan) -> bool:
    if has_global_access(user):
        return True
    user_id = getattr(user, "id", None)
    return bool(
        is_management_user(user)
        and user_id
        and user_id in {action_plan.owner_id, action_plan.anomaly.owner_id}
    )


def _require_action_plan_manager(user, action_plan: ActionPlan) -> None:
    if not _can_manage_action_plan(user, action_plan):
        raise PermissionDenied("Solo el responsable del plan o usuarios ADMIN pueden gestionarlo.")


def _require_action_assignee(user, action_item: ActionItem) -> None:
    if not can_execute_assignment(user, action_item.assigned_to_id):
        raise PermissionDenied("Solo el responsable asignado puede ejecutar esta accion.")



def _bump_version(instance) -> None:
    instance.row_version = (instance.row_version or 0) + 1



def build_action_item_code(*, action_plan: ActionPlan, sequence: int) -> str:
    return f"ACT-{action_plan.anomaly.code}-{int(sequence):02d}"[:80]



def snapshot_action_plan(action_plan: ActionPlan) -> dict:
    return {
        "id": str(action_plan.pk),
        "anomaly_id": str(action_plan.anomaly_id),
        "owner_id": str(action_plan.owner_id) if action_plan.owner_id else "",
        "status": action_plan.status,
        "approved_at": action_plan.approved_at.isoformat() if action_plan.approved_at else "",
    }



def snapshot_action_item(action_item: ActionItem) -> dict:
    return {
        "id": str(action_item.pk),
        "action_plan_id": str(action_item.action_plan_id),
        "code": action_item.code,
        "action_type_id": str(action_item.action_type_id),
        "priority_id": str(action_item.priority_id) if action_item.priority_id else "",
        "assigned_to_id": str(action_item.assigned_to_id) if action_item.assigned_to_id else "",
        "title": action_item.title,
        "description": action_item.description,
        "status": action_item.status,
        "effective_status": action_item.effective_status,
        "due_date": action_item.due_date.isoformat() if action_item.due_date else "",
        "completed_at": action_item.completed_at.isoformat() if action_item.completed_at else "",
        "is_mandatory": action_item.is_mandatory,
        "sequence": action_item.sequence,
        "expected_evidence": action_item.expected_evidence,
        "closure_comment": action_item.closure_comment,
    }



def snapshot_action_evidence(evidence: ActionEvidence) -> dict:
    return {
        "id": str(evidence.pk),
        "action_item_id": str(evidence.action_item_id),
        "evidence_type": evidence.evidence_type,
        "note": evidence.note,
        "has_file": bool(evidence.file),
    }



def _write_action_history(*, action_item: ActionItem, event_type: str, actor, comment: str, from_status: str = "", to_status: str = "", snapshot_data: dict | None = None):
    return ActionItemHistory.objects.create(
        action_item=action_item,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        comment=comment,
        changed_by=actor,
        changed_at=timezone.now(),
        snapshot_data=snapshot_data or {},
        created_by=actor,
        updated_by=actor,
    )



def _validate_action_plan_editable(action_plan: ActionPlan) -> None:
    if action_plan.status in {ActionPlanStatus.COMPLETED, ActionPlanStatus.CANCELLED}:
        raise ValidationError({"status": "El plan ya no admite cambios porque se encuentra finalizado o cancelado."})



def _validate_action_item_editable(action_item: ActionItem) -> None:
    if action_item.action_plan.status in {ActionPlanStatus.COMPLETED, ActionPlanStatus.CANCELLED}:
        raise ValidationError({"action_plan": "No puede modificar acciones de un plan finalizado o cancelado."})


@transaction.atomic
def create_action_plan(*, anomaly, user, data: dict, request_id: str = "") -> ActionPlan:
    if not has_global_access(user) and not (
        is_management_user(user) and anomaly.owner_id == getattr(user, "id", None)
    ):
        raise PermissionDenied("Solo el responsable asignado o usuarios ADMIN pueden crear el plan de accion.")

    if anomaly.action_plans.filter(status=ActionPlanStatus.ACTIVE).exists():
        raise ValidationError({"status": "La anomalia ya tiene un plan de accion activo."})

    requested_status = data.get("status") or ActionPlanStatus.DRAFT
    if requested_status != ActionPlanStatus.DRAFT:
        raise ValidationError({"status": "El plan debe crearse inicialmente en borrador."})

    action_plan = ActionPlan(
        anomaly=anomaly,
        owner=data.get("owner"),
        status=ActionPlanStatus.DRAFT,
        created_by=user,
        updated_by=user,
    )
    action_plan.full_clean()
    action_plan.save()

    record_audit_event(
        entity=action_plan,
        action="action_plan.created",
        actor=user,
        after_data=snapshot_action_plan(action_plan),
        request_id=_request_id(request_id),
    )
    return action_plan


@transaction.atomic
def update_action_plan(*, action_plan: ActionPlan, user, data: dict, request_id: str = "") -> ActionPlan:
    locked = ActionPlan.objects.select_for_update().select_related("anomaly").get(pk=action_plan.pk)
    _require_action_plan_manager(user, locked)
    _validate_action_plan_editable(locked)
    before = snapshot_action_plan(locked)

    if "owner" in data:
        locked.owner = data["owner"]

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    record_audit_event(
        entity=locked,
        action="action_plan.updated",
        actor=user,
        before_data=before,
        after_data=snapshot_action_plan(locked),
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def transition_action_plan(*, action_plan: ActionPlan, user, target_status: str, comment: str, request_id: str = "") -> ActionPlan:
    locked = ActionPlan.objects.select_for_update().select_related("anomaly").get(pk=action_plan.pk)
    _require_action_plan_manager(user, locked)

    if not comment or not comment.strip():
        raise ValidationError({"comment": "El comentario de transicion es obligatorio."})

    current_status = locked.status
    if target_status == current_status:
        raise ValidationError({"target_status": "El plan ya se encuentra en el estado indicado."})

    allowed_statuses = ALLOWED_ACTION_PLAN_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_statuses:
        raise ValidationError({"target_status": "La transicion del plan no es valida desde el estado actual."})

    if target_status == ActionPlanStatus.ACTIVE:
        if not locked.items.exists():
            raise ValidationError({"target_status": "Debe registrar al menos una accion antes de activar el plan."})
        active_qs = ActionPlan.objects.filter(anomaly=locked.anomaly, status=ActionPlanStatus.ACTIVE).exclude(pk=locked.pk)
        if active_qs.exists():
            raise ValidationError({"target_status": "La anomalia ya posee otro plan activo."})

    if target_status == ActionPlanStatus.COMPLETED:
        open_mandatory = locked.items.filter(is_mandatory=True).exclude(
            status__in=[ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED]
        )
        if open_mandatory.exists():
            raise ValidationError({"target_status": "No puede completar el plan mientras existan acciones obligatorias abiertas."})

    before = snapshot_action_plan(locked)
    locked.status = target_status
    locked.updated_by = user
    if target_status == ActionPlanStatus.ACTIVE:
        locked.approved_at = timezone.now()
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    record_audit_event(
        entity=locked,
        action="action_plan.transitioned",
        actor=user,
        before_data=before,
        after_data=snapshot_action_plan(locked) | {"comment": comment},
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def create_action_item(*, action_plan: ActionPlan, user, data: dict, request_id: str = "") -> ActionItem:
    locked_plan = ActionPlan.objects.select_for_update().select_related("anomaly", "anomaly__priority").get(pk=action_plan.pk)
    _require_action_plan_manager(user, locked_plan)
    _validate_action_plan_editable(locked_plan)

    sequence = data.get("sequence") or (locked_plan.items.count() + 1)
    item = ActionItem(
        action_plan=locked_plan,
        code=(data.get("code") or build_action_item_code(action_plan=locked_plan, sequence=sequence)),
        action_type=data["action_type"],
        priority=data.get("priority") or locked_plan.anomaly.priority,
        assigned_to=data.get("assigned_to"),
        title=data["title"],
        description=data.get("description", ""),
        due_date=data.get("due_date"),
        is_mandatory=data.get("is_mandatory", True),
        sequence=sequence,
        expected_evidence=data.get("expected_evidence", ""),
        closure_comment=data.get("closure_comment", ""),
        created_by=user,
        updated_by=user,
    )
    item.full_clean()
    item.save()

    _write_action_history(
        action_item=item,
        event_type=ActionHistoryEvent.CREATED,
        actor=user,
        comment="Accion creada.",
        to_status=item.status,
        snapshot_data=snapshot_action_item(item),
    )
    record_audit_event(
        entity=item,
        action="action_item.created",
        actor=user,
        after_data=snapshot_action_item(item),
        request_id=_request_id(request_id),
    )
    notify_action_item_assigned(action_item=item, actor=user, request_id=request_id)
    return item


@transaction.atomic
def update_action_item(*, action_item: ActionItem, user, data: dict, request_id: str = "") -> ActionItem:
    locked = ActionItem.objects.select_for_update().select_related("action_plan", "action_plan__anomaly").get(pk=action_item.pk)
    _require_action_plan_manager(user, locked.action_plan)
    _validate_action_item_editable(locked)
    before = snapshot_action_item(locked)
    previous_assigned_to_id = locked.assigned_to_id

    for field in (
        "code",
        "action_type",
        "priority",
        "assigned_to",
        "title",
        "description",
        "due_date",
        "is_mandatory",
        "sequence",
        "expected_evidence",
        "closure_comment",
    ):
        if field in data:
            setattr(locked, field, data[field])

    if not locked.code:
        locked.code = build_action_item_code(action_plan=locked.action_plan, sequence=locked.sequence)

    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    if previous_assigned_to_id != locked.assigned_to_id:
        dismiss_action_assignment_tasks(
            action_item=locked,
            actor=user,
            keep_user_id=locked.assigned_to_id,
            request_id=request_id,
        )
        notify_action_item_assigned(action_item=locked, actor=user, reassigned=True, request_id=request_id)
        event_type = ActionHistoryEvent.REASSIGNED
        history_comment = "Responsable de accion actualizado."
    else:
        event_type = ActionHistoryEvent.UPDATED
        history_comment = "Accion actualizada."

    _write_action_history(
        action_item=locked,
        event_type=event_type,
        actor=user,
        comment=history_comment,
        from_status=before["status"],
        to_status=locked.status,
        snapshot_data=snapshot_action_item(locked),
    )
    record_audit_event(
        entity=locked,
        action="action_item.updated",
        actor=user,
        before_data=before,
        after_data=snapshot_action_item(locked),
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def transition_action_item(
    *, action_item: ActionItem, user, target_status: str, comment: str, closure_comment: str = "", request_id: str = ""
) -> ActionItem:
    locked = ActionItem.objects.select_for_update().select_related("action_plan", "action_plan__anomaly").get(pk=action_item.pk)
    _validate_action_item_editable(locked)

    if not comment or not comment.strip():
        raise ValidationError({"comment": "El comentario de transicion es obligatorio."})

    if target_status == locked.status:
        raise ValidationError({"target_status": "La accion ya se encuentra en el estado indicado."})

    allowed_statuses = ALLOWED_ACTION_ITEM_TRANSITIONS.get(locked.status, set())
    if target_status not in allowed_statuses:
        raise ValidationError({"target_status": "La transicion de la accion no es valida desde el estado actual."})

    if target_status == ActionItemStatus.CANCELLED:
        _require_action_plan_manager(user, locked.action_plan)
    else:
        _require_action_assignee(user, locked)

    before = snapshot_action_item(locked)
    locked.status = target_status
    locked.updated_by = user
    if target_status == ActionItemStatus.COMPLETED:
        locked.completed_at = timezone.now()
        locked.closure_comment = closure_comment or comment
    elif target_status == ActionItemStatus.CANCELLED:
        locked.completed_at = None
        locked.closure_comment = closure_comment or comment
    else:
        locked.completed_at = None

    _bump_version(locked)
    locked.full_clean()
    locked.save()

    _write_action_history(
        action_item=locked,
        event_type=ActionHistoryEvent.STATUS_CHANGED,
        actor=user,
        comment=comment,
        from_status=before["status"],
        to_status=locked.status,
        snapshot_data=snapshot_action_item(locked),
    )
    record_audit_event(
        entity=locked,
        action="action_item.transitioned",
        actor=user,
        before_data=before,
        after_data=snapshot_action_item(locked) | {"comment": comment},
        request_id=_request_id(request_id),
    )
    sync_action_assignment_task_status(action_item=locked, actor=user, request_id=request_id)
    return locked


@transaction.atomic
def add_action_evidence(*, action_item: ActionItem, user, data: dict, request_id: str = "") -> ActionEvidence:
    locked = ActionItem.objects.select_related("action_plan", "action_plan__anomaly").get(pk=action_item.pk)
    _require_action_assignee(user, locked)

    if not data.get("file") and not (data.get("note") or "").strip():
        raise ValidationError({"note": "Debe adjuntar un archivo o informar una nota de evidencia."})

    if data.get("file"):
        validate_evidence_file(data["file"])

    evidence = ActionEvidence(
        action_item=locked,
        evidence_type=data.get("evidence_type") or "file",
        file=data.get("file"),
        note=data.get("note", ""),
        created_by=user,
        updated_by=user,
    )
    evidence.full_clean()
    evidence.save()

    _write_action_history(
        action_item=locked,
        event_type=ActionHistoryEvent.EVIDENCE_ADDED,
        actor=user,
        comment=evidence.note or "Evidencia agregada.",
        from_status=locked.status,
        to_status=locked.status,
        snapshot_data=snapshot_action_evidence(evidence),
    )
    record_audit_event(
        entity=evidence,
        action="action_item.evidence_added",
        actor=user,
        after_data=snapshot_action_evidence(evidence),
        request_id=_request_id(request_id),
    )
    return evidence

