from __future__ import annotations

from datetime import datetime, time

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.actions.models import ActionItemStatus
from apps.anomalies.models import ParticipantRole
from apps.audit.services import record_audit_event
from apps.notifications.models import (
    DeliveryStatus,
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationRecipient,
    NotificationStatus,
    NotificationTaskType,
    RecipientTaskStatus,
)

PARTICIPATION_TASK_TYPE_BY_ROLE = {
    ParticipantRole.ANALYST: NotificationTaskType.ANALYSIS_PARTICIPATION,
    ParticipantRole.IMPLEMENTER: NotificationTaskType.TREATMENT_PARTICIPATION,
    ParticipantRole.REVIEWER: NotificationTaskType.VERIFICATION_PARTICIPATION,
    ParticipantRole.VERIFIER: NotificationTaskType.VERIFICATION_PARTICIPATION,
}

ACTION_ITEM_TASK_STATUS_MAP = {
    ActionItemStatus.PENDING: RecipientTaskStatus.PENDING,
    ActionItemStatus.IN_PROGRESS: RecipientTaskStatus.IN_PROGRESS,
    ActionItemStatus.COMPLETED: RecipientTaskStatus.COMPLETED,
    ActionItemStatus.CANCELLED: RecipientTaskStatus.DISMISSED,
}


def _request_id(value: str | None) -> str:
    return (value or "").strip()



def _bump_version(instance) -> None:
    instance.row_version = (instance.row_version or 0) + 1



def _unique_active_users(users) -> list:
    unique_users = []
    seen_ids = set()
    for user in users:
        if not user or not getattr(user, "pk", None) or not getattr(user, "is_active", True):
            continue
        if user.pk in seen_ids:
            continue
        seen_ids.add(user.pk)
        unique_users.append(user)
    return unique_users



def _action_due_at(action_item):
    if not action_item.due_date:
        return None
    due_datetime = datetime.combine(action_item.due_date, time(23, 59, 59))
    return timezone.make_aware(due_datetime, timezone.get_current_timezone())



@transaction.atomic
def create_internal_notification(
    *,
    recipients: list,
    title: str,
    body: str,
    source_type: str,
    source_id,
    actor=None,
    category: str = NotificationCategory.INFO,
    template_code: str = "",
    is_task: bool = False,
    task_type: str = NotificationTaskType.NONE,
    action_url: str = "",
    due_at=None,
    context_data: dict | None = None,
    request_id: str = "",
    email_enabled: bool = False,
):
    users = _unique_active_users(recipients)
    if not users:
        return None

    email_users = [
        user
        for user in users
        if email_enabled
        and settings.EMAIL_NOTIFICATIONS_ENABLED
        and getattr(user, "email_notifications_enabled", False)
        and bool((getattr(user, "email", "") or "").strip())
    ]

    notification = Notification(
        source_type=source_type,
        source_id=source_id,
        template_code=template_code,
        title=title,
        body=body,
        category=category,
        is_task=is_task,
        task_type=task_type if is_task else NotificationTaskType.NONE,
        action_url=action_url,
        due_at=due_at,
        status=NotificationStatus.PENDING if email_users else NotificationStatus.SENT,
        context_data=context_data or {},
        created_by=actor,
        updated_by=actor,
    )
    notification.full_clean()
    notification.save()

    assigned_at = timezone.now() if is_task else None
    task_status = RecipientTaskStatus.PENDING if is_task else RecipientTaskStatus.NONE
    recipient_objects = [
        NotificationRecipient(
            notification=notification,
            user=user,
            channel=NotificationChannel.IN_APP,
            delivery_status=DeliveryStatus.DELIVERED,
            task_status=task_status,
            assigned_at=assigned_at,
            created_by=actor,
            updated_by=actor,
        )
        for user in users
    ]
    recipient_objects.extend(
        NotificationRecipient(
            notification=notification,
            user=user,
            channel=NotificationChannel.EMAIL,
            destination=user.email.strip(),
            delivery_status=DeliveryStatus.PENDING,
            task_status=task_status,
            assigned_at=assigned_at,
            created_by=actor,
            updated_by=actor,
        )
        for user in email_users
    )
    created_recipients = NotificationRecipient.objects.bulk_create(recipient_objects)

    record_audit_event(
        entity=notification,
        action="notification.created",
        actor=actor,
        after_data={
            "notification_id": str(notification.pk),
            "recipient_ids": [str(recipient.user_id) for recipient in created_recipients],
            "email_recipient_ids": [
                str(recipient.user_id)
                for recipient in created_recipients
                if recipient.channel == NotificationChannel.EMAIL
            ],
            "task_type": notification.task_type,
        },
        request_id=_request_id(request_id),
    )
    return notification


@transaction.atomic
def mark_notification_as_read(*, recipient: NotificationRecipient, user, request_id: str = "") -> NotificationRecipient:
    locked = NotificationRecipient.objects.select_for_update().select_related("notification").get(pk=recipient.pk)
    if locked.user_id != user.pk and not user.is_superuser:
        raise PermissionDenied("Solo puede marcar como leidas sus propias notificaciones.")

    if not locked.read_at:
        locked.read_at = timezone.now()
    locked.delivery_status = DeliveryStatus.READ
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    record_audit_event(
        entity=locked.notification,
        action="notification.read",
        actor=user,
        after_data={"recipient_id": str(locked.pk), "read_at": locked.read_at},
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def resolve_notification_task(
    *, recipient: NotificationRecipient, user, task_status: str, comment: str = "", request_id: str = ""
) -> NotificationRecipient:
    locked = NotificationRecipient.objects.select_for_update().select_related("notification").get(pk=recipient.pk)
    if locked.user_id != user.pk and not user.is_superuser:
        raise PermissionDenied("Solo puede gestionar sus propias tareas internas.")
    if not locked.notification.is_task:
        raise ValidationError({"task_status": "La notificacion seleccionada no representa una tarea."})

    if task_status not in {
        RecipientTaskStatus.IN_PROGRESS,
        RecipientTaskStatus.COMPLETED,
        RecipientTaskStatus.DISMISSED,
    }:
        raise ValidationError({"task_status": "El estado de tarea solicitado no es valido."})

    locked.task_status = task_status
    locked.resolved_at = timezone.now() if task_status in {RecipientTaskStatus.COMPLETED, RecipientTaskStatus.DISMISSED} else None
    locked.updated_by = user
    _bump_version(locked)
    locked.full_clean()
    locked.save()

    record_audit_event(
        entity=locked.notification,
        action="notification.task_resolved",
        actor=user,
        after_data={
            "recipient_id": str(locked.pk),
            "task_status": locked.task_status,
            "comment": comment,
        },
        request_id=_request_id(request_id),
    )
    return locked


@transaction.atomic
def dismiss_action_assignment_tasks(*, action_item, actor=None, keep_user_id=None, request_id: str = "") -> None:
    queryset = NotificationRecipient.objects.select_for_update().filter(
        notification__source_type="actions.actionitem",
        notification__source_id=action_item.pk,
        notification__task_type=NotificationTaskType.ACTION_ASSIGNMENT,
        task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
    )
    if keep_user_id:
        queryset = queryset.exclude(user_id=keep_user_id)

    recipients = list(queryset.select_related("notification"))
    if not recipients:
        return

    now = timezone.now()
    for recipient in recipients:
        recipient.task_status = RecipientTaskStatus.DISMISSED
        recipient.resolved_at = now
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        ["task_status", "resolved_at", "updated_by", "row_version", "updated_at"],
    )
    for recipient in recipients:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_dismissed",
            actor=actor,
            after_data={"recipient_id": str(recipient.pk), "task_status": recipient.task_status},
            request_id=_request_id(request_id),
        )


@transaction.atomic
def sync_action_assignment_task_status(*, action_item, actor=None, request_id: str = "") -> None:
    task_status = ACTION_ITEM_TASK_STATUS_MAP.get(action_item.status, RecipientTaskStatus.PENDING)
    is_terminal = task_status in {RecipientTaskStatus.COMPLETED, RecipientTaskStatus.DISMISSED}
    now = timezone.now()

    queryset = NotificationRecipient.objects.select_for_update().filter(
        notification__source_type="actions.actionitem",
        notification__source_id=action_item.pk,
        notification__task_type=NotificationTaskType.ACTION_ASSIGNMENT,
    )
    recipients = list(queryset.select_related("notification"))
    if not recipients:
        return

    for recipient in recipients:
        recipient.task_status = task_status
        recipient.resolved_at = now if is_terminal else None
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        ["task_status", "resolved_at", "updated_by", "row_version", "updated_at"],
    )
    for recipient in recipients:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_synced",
            actor=actor,
            after_data={"recipient_id": str(recipient.pk), "task_status": recipient.task_status},
            request_id=_request_id(request_id),
        )



def notify_anomaly_created(*, anomaly, actor=None, request_id: str = ""):
    current_responsible = anomaly.owner
    responsible_label = current_responsible.full_name if current_responsible else "Sin responsable asignado"
    detected_at = timezone.localtime(anomaly.detected_at).strftime("%d/%m/%Y %H:%M")
    return create_internal_notification(
        recipients=[anomaly.reporter],
        title=f"Anomalía {anomaly.code} registrada correctamente",
        body=(
            f"Hola {anomaly.reporter.full_name},\n\n"
            f"La anomalía {anomaly.code} fue generada correctamente.\n"
            f"Título: {anomaly.title}\n"
            f"Sector: {anomaly.area.name}\n"
            f"Fecha y hora: {detected_at}\n"
            f"Estado inicial: {anomaly.get_current_status_display()}\n"
            f"Responsable actual: {responsible_label}."
        ),
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        actor=actor,
        category=NotificationCategory.ANOMALY,
        template_code="anomaly_created",
        action_url=f"/anomalies/{anomaly.pk}",
        context_data={
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "initial_status": anomaly.current_status,
            "detected_at": anomaly.detected_at.isoformat(),
            "current_responsible_id": str(current_responsible.pk) if current_responsible else "",
        },
        request_id=request_id,
        email_enabled=True,
    )



def notify_action_item_assigned(*, action_item, actor=None, reassigned: bool = False, request_id: str = ""):
    if not action_item.assigned_to_id:
        return None
    verb = "reasignada" if reassigned else "asignada"
    due_label = action_item.due_date.isoformat() if action_item.due_date else "sin fecha compromiso"
    return create_internal_notification(
        recipients=[action_item.assigned_to],
        title=f"Accion {action_item.code} {verb}",
        body=f"{action_item.title}. Fecha compromiso: {due_label}.",
        source_type="actions.actionitem",
        source_id=action_item.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        is_task=True,
        task_type=NotificationTaskType.ACTION_ASSIGNMENT,
        action_url=f"/api/v1/actions/items/{action_item.pk}/",
        due_at=_action_due_at(action_item),
        context_data={
            "action_item_id": str(action_item.pk),
            "action_code": action_item.code,
            "anomaly_id": str(action_item.action_plan.anomaly_id),
            "anomaly_code": action_item.action_plan.anomaly.code,
            "assigned_to_id": str(action_item.assigned_to_id),
        },
        request_id=request_id,
    )



def notify_participation_request(*, anomaly, participant, actor=None, request_id: str = ""):
    task_type = PARTICIPATION_TASK_TYPE_BY_ROLE.get(participant.role)
    if not task_type:
        return None
    return create_internal_notification(
        recipients=[participant.user],
        title=f"Participacion requerida en {anomaly.code}",
        body=f"Fue convocado como {participant.get_role_display()} en la anomalia {anomaly.title}.",
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        actor=actor,
        category=NotificationCategory.PARTICIPATION,
        is_task=True,
        task_type=task_type,
        action_url=f"/api/v1/anomalies/{anomaly.pk}/",
        due_at=anomaly.due_at,
        context_data={
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "participant_id": str(participant.pk),
            "participant_role": participant.role,
        },
        request_id=request_id,
    )
