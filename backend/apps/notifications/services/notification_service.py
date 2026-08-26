from __future__ import annotations

from datetime import datetime, time

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.actions.models import ActionItemStatus, TreatmentTaskStatus
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

TREATMENT_TASK_STATUS_MAP = {
    TreatmentTaskStatus.PENDING: RecipientTaskStatus.PENDING,
    TreatmentTaskStatus.IN_PROGRESS: RecipientTaskStatus.IN_PROGRESS,
    TreatmentTaskStatus.COMPLETED: RecipientTaskStatus.COMPLETED,
    TreatmentTaskStatus.CANCELLED: RecipientTaskStatus.DISMISSED,
}

FINDING_MANAGEMENT_TEMPLATE = "finding_management_assigned"
TREATMENT_EFFECTIVENESS_TEMPLATE = "treatment_effectiveness_assigned"
OBSERVATION_EFFECTIVENESS_TEMPLATE = "observation_effectiveness_assigned"
ANOMALY_CLOSED_TEMPLATE = "anomaly_closed"
TREATMENT_CLOSED_TEMPLATE = "treatment_closed"
TREATMENT_REPORTER_CLOSURE_TEMPLATE = "anomalies_closed_by_treatment"
TREATMENT_LEARNED_LESSON_TEMPLATE = "treatment_learned_lesson_published"
TREATMENT_NOT_EFFECTIVE_TEMPLATE = "treatment_not_effective"
OBSERVATION_NOT_EFFECTIVE_TEMPLATE = "observation_not_effective"


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


def _event_notification_exists(
    *,
    source_type: str,
    source_id,
    template_code: str,
    event_key: str,
    recipient_id=None,
) -> bool:
    queryset = Notification.objects.filter(
        source_type=source_type,
        source_id=source_id,
        template_code=template_code,
    ).order_by("-created_at")
    if recipient_id:
        queryset = queryset.filter(
            recipients__user_id=recipient_id,
            recipients__channel=NotificationChannel.IN_APP,
        )
    return any(
        notification.context_data.get("event_key") == event_key
        for notification in queryset[:20]
    )


def _treatment_involved_users(treatment) -> list:
    users = [getattr(treatment, "responsible", None)]
    users.extend(
        participant.user
        for participant in treatment.participants.select_related("user").all()
    )
    users.extend(
        task.responsible
        for task in treatment.tasks.select_related("responsible").all()
        if task.responsible_id
    )
    users.append(getattr(treatment, "effectiveness_responsible", None))
    return _unique_active_users(users)



def _action_due_at(action_item):
    if not action_item.due_date:
        return None
    due_datetime = datetime.combine(action_item.due_date, time(23, 59, 59))
    return timezone.make_aware(due_datetime, timezone.get_current_timezone())


def _treatment_task_due_at(treatment_task):
    if not treatment_task.execution_date:
        return None
    due_datetime = datetime.combine(treatment_task.execution_date, time(23, 59, 59))
    return timezone.make_aware(due_datetime, timezone.get_current_timezone())


def _date_due_at(due_date):
    if not due_date:
        return None
    due_datetime = datetime.combine(due_date, time(23, 59, 59))
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


@transaction.atomic
def dismiss_treatment_task_assignment_tasks(
    *, treatment_task, actor=None, keep_user_id=None, request_id: str = ""
) -> None:
    queryset = NotificationRecipient.objects.select_for_update().filter(
        notification__source_type="actions.treatmenttask",
        notification__source_id=treatment_task.pk,
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
        if recipient.channel == NotificationChannel.EMAIL and recipient.delivery_status == DeliveryStatus.PENDING:
            recipient.delivery_status = DeliveryStatus.SKIPPED
            recipient.delivery_error = "Asignación reemplazada antes del envío."
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        [
            "task_status",
            "resolved_at",
            "delivery_status",
            "delivery_error",
            "updated_by",
            "row_version",
            "updated_at",
        ],
    )
    notification_ids = {recipient.notification_id for recipient in recipients}
    Notification.objects.filter(pk__in=notification_ids).update(
        status=NotificationStatus.SENT,
        row_version=F("row_version") + 1,
        updated_at=now,
    )
    for recipient in recipients:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_dismissed",
            actor=actor,
            after_data={
                "recipient_id": str(recipient.pk),
                "task_status": recipient.task_status,
                "reason": "treatment_task_reassigned",
            },
            request_id=_request_id(request_id),
        )


@transaction.atomic
def sync_treatment_task_assignment_status(*, treatment_task, actor=None, request_id: str = "") -> None:
    task_status = TREATMENT_TASK_STATUS_MAP.get(treatment_task.status, RecipientTaskStatus.PENDING)
    is_terminal = task_status in {RecipientTaskStatus.COMPLETED, RecipientTaskStatus.DISMISSED}
    now = timezone.now()
    recipients = list(
        NotificationRecipient.objects.select_for_update()
        .select_related("notification")
        .filter(
            notification__source_type="actions.treatmenttask",
            notification__source_id=treatment_task.pk,
            notification__task_type=NotificationTaskType.ACTION_ASSIGNMENT,
            user_id=treatment_task.responsible_id,
        )
    )
    if not recipients:
        return

    for recipient in recipients:
        recipient.task_status = task_status
        recipient.resolved_at = now if is_terminal else None
        if (
            is_terminal
            and recipient.channel == NotificationChannel.EMAIL
            and recipient.delivery_status == DeliveryStatus.PENDING
        ):
            recipient.delivery_status = DeliveryStatus.SKIPPED
            recipient.delivery_error = "La tarea finalizó antes del envío de la asignación."
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        [
            "task_status",
            "resolved_at",
            "delivery_status",
            "delivery_error",
            "updated_by",
            "row_version",
            "updated_at",
        ],
    )
    notification_ids = {recipient.notification_id for recipient in recipients}
    notification_updates = {
        "due_at": _treatment_task_due_at(treatment_task),
        "row_version": F("row_version") + 1,
        "updated_at": now,
    }
    if is_terminal:
        notification_updates["status"] = NotificationStatus.SENT
    Notification.objects.filter(pk__in=notification_ids).update(**notification_updates)
    for recipient in recipients:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_synced",
            actor=actor,
            after_data={"recipient_id": str(recipient.pk), "task_status": recipient.task_status},
            request_id=_request_id(request_id),
        )


def _dismiss_previous_effectiveness_tasks(
    *, source_type: str, source_id, template_code: str, actor=None, keep_notification_id=None, request_id: str = ""
) -> None:
    active_in_app = list(
        NotificationRecipient.objects.select_for_update()
        .select_related("notification")
        .filter(
            channel=NotificationChannel.IN_APP,
            notification__source_type=source_type,
            notification__source_id=source_id,
            notification__template_code=template_code,
            notification__task_type=NotificationTaskType.VERIFICATION_PARTICIPATION,
            task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
        )
        .exclude(notification_id=keep_notification_id)
    )
    if not active_in_app:
        return

    notification_ids = [recipient.notification_id for recipient in active_in_app]
    recipients = list(
        NotificationRecipient.objects.select_for_update().filter(notification_id__in=notification_ids)
    )
    now = timezone.now()
    for recipient in recipients:
        if recipient.task_status in {RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS}:
            recipient.task_status = RecipientTaskStatus.DISMISSED
            recipient.resolved_at = now
        if recipient.channel == NotificationChannel.EMAIL and recipient.delivery_status == DeliveryStatus.PENDING:
            recipient.delivery_status = DeliveryStatus.SKIPPED
            recipient.delivery_error = "Asignación de verificación reemplazada antes del envío."
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        [
            "task_status",
            "resolved_at",
            "delivery_status",
            "delivery_error",
            "updated_by",
            "row_version",
            "updated_at",
        ],
    )
    Notification.objects.filter(pk__in=notification_ids).update(
        status=NotificationStatus.SENT,
        row_version=F("row_version") + 1,
        updated_at=now,
    )
    for recipient in active_in_app:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_dismissed",
            actor=actor,
            after_data={
                "recipient_id": str(recipient.pk),
                "task_status": RecipientTaskStatus.DISMISSED,
                "reason": "effectiveness_assignment_replaced",
            },
            request_id=_request_id(request_id),
        )


def _matching_effectiveness_task(
    *, source_type: str, source_id, template_code: str, responsible, due_date
):
    due_date_value = due_date.isoformat() if due_date else ""
    candidates = (
        NotificationRecipient.objects.select_for_update()
        .select_related("notification")
        .filter(
            user=responsible,
            channel=NotificationChannel.IN_APP,
            notification__source_type=source_type,
            notification__source_id=source_id,
            notification__template_code=template_code,
            notification__task_type=NotificationTaskType.VERIFICATION_PARTICIPATION,
            task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
        )
        .order_by("-created_at")
    )
    return next(
        (
            recipient
            for recipient in candidates
            if recipient.notification.context_data.get("due_date") == due_date_value
        ),
        None,
    )


@transaction.atomic
def _complete_effectiveness_tasks(
    *, source_type: str, source_id, template_code: str, actor=None, request_id: str = ""
) -> None:
    recipients = list(
        NotificationRecipient.objects.select_for_update()
        .select_related("notification")
        .filter(
            notification__source_type=source_type,
            notification__source_id=source_id,
            notification__template_code=template_code,
            notification__task_type=NotificationTaskType.VERIFICATION_PARTICIPATION,
            task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
        )
    )
    if not recipients:
        return

    now = timezone.now()
    for recipient in recipients:
        recipient.task_status = RecipientTaskStatus.COMPLETED
        recipient.resolved_at = now
        if recipient.channel == NotificationChannel.EMAIL and recipient.delivery_status == DeliveryStatus.PENDING:
            recipient.delivery_status = DeliveryStatus.SKIPPED
            recipient.delivery_error = "La verificación se completó antes del envío de la asignación."
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        [
            "task_status",
            "resolved_at",
            "delivery_status",
            "delivery_error",
            "updated_by",
            "row_version",
            "updated_at",
        ],
    )
    notification_ids = {recipient.notification_id for recipient in recipients}
    Notification.objects.filter(pk__in=notification_ids).update(
        status=NotificationStatus.SENT,
        row_version=F("row_version") + 1,
        updated_at=now,
    )
    for recipient in recipients:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_synced",
            actor=actor,
            after_data={"recipient_id": str(recipient.pk), "task_status": RecipientTaskStatus.COMPLETED},
            request_id=_request_id(request_id),
        )


def _dismiss_previous_finding_management_tasks(
    *, anomaly, actor=None, keep_notification_id=None, request_id: str = ""
) -> None:
    active_in_app = list(
        NotificationRecipient.objects.select_for_update()
        .select_related("notification")
        .filter(
            channel=NotificationChannel.IN_APP,
            notification__source_type="anomalies.anomaly",
            notification__source_id=anomaly.pk,
            notification__template_code=FINDING_MANAGEMENT_TEMPLATE,
            notification__task_type=NotificationTaskType.FINDING_MANAGEMENT,
            task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
        )
        .exclude(notification_id=keep_notification_id)
    )
    if not active_in_app:
        return

    notification_ids = [recipient.notification_id for recipient in active_in_app]
    recipients = list(
        NotificationRecipient.objects.select_for_update().filter(notification_id__in=notification_ids)
    )
    now = timezone.now()
    for recipient in recipients:
        if recipient.task_status in {RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS}:
            recipient.task_status = RecipientTaskStatus.DISMISSED
            recipient.resolved_at = now
        if recipient.channel == NotificationChannel.EMAIL and recipient.delivery_status == DeliveryStatus.PENDING:
            recipient.delivery_status = DeliveryStatus.SKIPPED
            recipient.delivery_error = "Asignación reemplazada antes del envío."
        recipient.updated_by = actor
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now

    NotificationRecipient.objects.bulk_update(
        recipients,
        [
            "task_status",
            "resolved_at",
            "delivery_status",
            "delivery_error",
            "updated_by",
            "row_version",
            "updated_at",
        ],
    )
    for recipient in active_in_app:
        record_audit_event(
            entity=recipient.notification,
            action="notification.task_dismissed",
            actor=actor,
            after_data={
                "recipient_id": str(recipient.pk),
                "task_status": RecipientTaskStatus.DISMISSED,
                "reason": "finding_responsible_reassigned",
            },
            request_id=_request_id(request_id),
        )


@transaction.atomic
def notify_finding_management_assigned(
    *,
    anomaly,
    responsible,
    actor=None,
    request_id: str = "",
    treatment=None,
):
    from apps.anomalies.services.classification_rules import is_immediate_action_anomaly

    severity_id = str(anomaly.severity_id or "")
    is_observation = is_immediate_action_anomaly(anomaly)
    is_observation_treatment = bool(
        is_observation and anomaly.observation_resolution_path == "TREATMENT_PENDING"
    )
    management_path = (
        "configured_treatment"
        if treatment is not None
        else "observation_treatment"
        if is_observation_treatment
        else "observation_or_treatment"
        if is_observation
        else "treatment"
    )
    matching_recipient = None
    if responsible:
        active_recipients = (
            NotificationRecipient.objects.select_for_update()
            .select_related("notification")
            .filter(
                user=responsible,
                channel=NotificationChannel.IN_APP,
                notification__source_type="anomalies.anomaly",
                notification__source_id=anomaly.pk,
                notification__template_code=FINDING_MANAGEMENT_TEMPLATE,
                notification__task_type=NotificationTaskType.FINDING_MANAGEMENT,
                task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
            )
            .order_by("-created_at")
        )
        matching_recipient = next(
            (
                recipient
                for recipient in active_recipients
                if recipient.notification.context_data.get("severity_id") == severity_id
                and recipient.notification.context_data.get("management_path") == management_path
            ),
            None,
        )

    _dismiss_previous_finding_management_tasks(
        anomaly=anomaly,
        actor=actor,
        keep_notification_id=matching_recipient.notification_id if matching_recipient else None,
        request_id=request_id,
    )
    if matching_recipient:
        return matching_recipient.notification
    if not responsible:
        return None

    if treatment is not None:
        linked_count = treatment.anomaly_links.count()
        title = f"Tratamiento {treatment.code} conformado por Calidad"
        instruction = (
            f"Calidad conformó el tratamiento con {linked_count} anomalía"
            f"{'s' if linked_count != 1 else ''}. Debes convocar a los participantes y realizar su gestión."
        )
        action_url = f"/treatments?treatment={treatment.pk}"
    elif is_observation_treatment:
        title = f"Tratamiento requerido para la observación TRT {anomaly.code}"
        instruction = "La observación fue marcada como plausible de tratamiento. Debes crear o coordinar su tratamiento."
        action_url = f"/treatments?anomaly={anomaly.pk}"
    elif is_observation:
        title = f"Gestión requerida para la observación {anomaly.code}"
        instruction = (
            "Debes revisar el hallazgo y definir si corresponde gestionarlo como observación directa "
            "o derivarlo a un tratamiento."
        )
        action_url = f"/anomalies/{anomaly.pk}"
    else:
        title = f"Tratamiento requerido para la anomalía {anomaly.code}"
        instruction = "Debes crear y coordinar el tratamiento, convocando a los participantes necesarios."
        action_url = f"/treatments?anomaly={anomaly.pk}"

    return create_internal_notification(
        recipients=[responsible],
        title=title,
        body=(
            f"Hola {responsible.full_name},\n\n"
            f"Fuiste designado responsable del hallazgo {anomaly.code}.\n"
            f"Clasificación: {anomaly.severity.name}\n"
            f"Título: {anomaly.title}\n"
            f"Sector: {anomaly.area.name}\n\n"
            f"{instruction}"
        ),
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        template_code=FINDING_MANAGEMENT_TEMPLATE,
        is_task=True,
        task_type=NotificationTaskType.FINDING_MANAGEMENT,
        action_url=action_url,
        due_at=anomaly.due_at,
        context_data={
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "severity_id": severity_id,
            "severity_code": anomaly.severity.code,
            "responsible_id": str(responsible.pk),
            "management_path": management_path,
            "treatment_id": str(treatment.pk) if treatment is not None else "",
            "treatment_code": treatment.code if treatment is not None else "",
        },
        request_id=request_id,
        email_enabled=True,
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
        body=(
            f"Hola {action_item.assigned_to.full_name},\n\n"
            f"Se te asignó la acción {action_item.code or action_item.title}.\n"
            f"Título: {action_item.title}\n"
            f"Descripción: {action_item.description or 'Sin descripción'}\n"
            f"Anomalía: {action_item.action_plan.anomaly.code}\n"
            f"Fecha compromiso: {due_label}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para consultar y gestionar la acción."
        ),
        source_type="actions.actionitem",
        source_id=action_item.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        is_task=True,
        task_type=NotificationTaskType.ACTION_ASSIGNMENT,
        action_url="/actions/mine",
        due_at=_action_due_at(action_item),
        context_data={
            "action_item_id": str(action_item.pk),
            "action_code": action_item.code,
            "anomaly_id": str(action_item.action_plan.anomaly_id),
            "anomaly_code": action_item.action_plan.anomaly.code,
            "assigned_to_id": str(action_item.assigned_to_id),
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


def notify_treatment_task_assigned(*, treatment_task, actor=None, reassigned: bool = False, request_id: str = ""):
    if not treatment_task.responsible_id:
        return None

    treatment = treatment_task.treatment
    verb = "reasignada" if reassigned else "asignada"
    execution_label = (
        treatment_task.execution_date.strftime("%d/%m/%Y")
        if treatment_task.execution_date
        else "Sin fecha definida"
    )
    anomaly_codes = list(
        treatment_task.anomaly_links.select_related("anomaly")
        .order_by("anomaly__code")
        .values_list("anomaly__code", flat=True)
    )
    anomaly_label = ", ".join(anomaly_codes) or treatment.primary_anomaly.code
    return create_internal_notification(
        recipients=[treatment_task.responsible],
        title=f"Tarea {treatment_task.code or treatment_task.title} {verb}",
        body=(
            f"Hola {treatment_task.responsible.full_name},\n\n"
            f"Se te asignó la tarea {treatment_task.code or treatment_task.title} del tratamiento {treatment.code}.\n"
            f"Título: {treatment_task.title}\n"
            f"Descripción: {treatment_task.description}\n"
            f"Anomalía(s): {anomaly_label}\n"
            f"Fecha de ejecución: {execution_label}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para consultar y gestionar la tarea."
        ),
        source_type="actions.treatmenttask",
        source_id=treatment_task.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        template_code="treatment_task_assigned",
        is_task=True,
        task_type=NotificationTaskType.ACTION_ASSIGNMENT,
        action_url="/actions/mine",
        due_at=_treatment_task_due_at(treatment_task),
        context_data={
            "treatment_id": str(treatment.pk),
            "treatment_code": treatment.code,
            "treatment_task_id": str(treatment_task.pk),
            "treatment_task_code": treatment_task.code,
            "responsible_id": str(treatment_task.responsible_id),
            "anomaly_codes": anomaly_codes,
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


@transaction.atomic
def notify_treatment_effectiveness_assigned(*, treatment, actor=None, request_id: str = ""):
    responsible = treatment.effectiveness_responsible
    due_date = treatment.effectiveness_evaluation_date
    if not responsible or not due_date:
        return None

    matching_recipient = _matching_effectiveness_task(
        source_type="actions.treatment",
        source_id=treatment.pk,
        template_code=TREATMENT_EFFECTIVENESS_TEMPLATE,
        responsible=responsible,
        due_date=due_date,
    )
    _dismiss_previous_effectiveness_tasks(
        source_type="actions.treatment",
        source_id=treatment.pk,
        template_code=TREATMENT_EFFECTIVENESS_TEMPLATE,
        actor=actor,
        keep_notification_id=matching_recipient.notification_id if matching_recipient else None,
        request_id=request_id,
    )
    if matching_recipient:
        return matching_recipient.notification

    anomaly_codes = list(
        treatment.anomaly_links.select_related("anomaly")
        .order_by("anomaly__code")
        .values_list("anomaly__code", flat=True)
    )
    anomaly_label = ", ".join(anomaly_codes) or treatment.primary_anomaly.code
    due_label = due_date.strftime("%d/%m/%Y")
    return create_internal_notification(
        recipients=[responsible],
        title=f"Verificación de eficacia asignada: {treatment.code}",
        body=(
            f"Hola {responsible.full_name},\n\n"
            f"Fuiste designado para verificar la eficacia del tratamiento {treatment.code}.\n"
            f"Anomalía(s): {anomaly_label}\n"
            f"Fecha de evaluación: {due_label}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para realizar la verificación."
        ),
        source_type="actions.treatment",
        source_id=treatment.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        template_code=TREATMENT_EFFECTIVENESS_TEMPLATE,
        is_task=True,
        task_type=NotificationTaskType.VERIFICATION_PARTICIPATION,
        action_url=f"/treatments?treatment={treatment.pk}",
        due_at=_date_due_at(due_date),
        context_data={
            "treatment_id": str(treatment.pk),
            "treatment_code": treatment.code,
            "responsible_id": str(responsible.pk),
            "due_date": due_date.isoformat(),
            "anomaly_codes": anomaly_codes or [treatment.primary_anomaly.code],
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


@transaction.atomic
def notify_observation_effectiveness_assigned(*, anomaly, immediate_action, actor=None, request_id: str = ""):
    responsible = immediate_action.responsible
    due_date = immediate_action.effectiveness_due_at
    if not responsible or not due_date:
        return None

    matching_recipient = _matching_effectiveness_task(
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        template_code=OBSERVATION_EFFECTIVENESS_TEMPLATE,
        responsible=responsible,
        due_date=due_date,
    )
    _dismiss_previous_effectiveness_tasks(
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        template_code=OBSERVATION_EFFECTIVENESS_TEMPLATE,
        actor=actor,
        keep_notification_id=matching_recipient.notification_id if matching_recipient else None,
        request_id=request_id,
    )
    if matching_recipient:
        return matching_recipient.notification

    due_label = due_date.strftime("%d/%m/%Y")
    return create_internal_notification(
        recipients=[responsible],
        title=f"Verificación de eficacia asignada: {anomaly.code}",
        body=(
            f"Hola {responsible.full_name},\n\n"
            f"Debes verificar la eficacia de la observación {anomaly.code} - {anomaly.title}.\n"
            f"Acción realizada: {immediate_action.actions_taken}\n"
            f"Fecha de verificación: {due_label}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para realizar la verificación."
        ),
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        template_code=OBSERVATION_EFFECTIVENESS_TEMPLATE,
        is_task=True,
        task_type=NotificationTaskType.VERIFICATION_PARTICIPATION,
        action_url=f"/anomalies/{anomaly.pk}",
        due_at=_date_due_at(due_date),
        context_data={
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "responsible_id": str(responsible.pk),
            "due_date": due_date.isoformat(),
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


def complete_treatment_effectiveness_assignment(*, treatment, actor=None, request_id: str = "") -> None:
    _complete_effectiveness_tasks(
        source_type="actions.treatment",
        source_id=treatment.pk,
        template_code=TREATMENT_EFFECTIVENESS_TEMPLATE,
        actor=actor,
        request_id=request_id,
    )


def complete_observation_effectiveness_assignment(*, anomaly, actor=None, request_id: str = "") -> None:
    _complete_effectiveness_tasks(
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        template_code=OBSERVATION_EFFECTIVENESS_TEMPLATE,
        actor=actor,
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


def notify_treatment_participant_invited(*, treatment, participant, actor=None, request_id: str = ""):
    scheduled_label = "Sin fecha programada"
    if treatment.scheduled_for:
        scheduled_label = timezone.localtime(treatment.scheduled_for).strftime("%d/%m/%Y %H:%M")
    location_label = (treatment.treatment_location or "").strip() or "Sin lugar definido"
    anomaly = treatment.primary_anomaly
    return create_internal_notification(
        recipients=[participant.user],
        title=f"Invitación al tratamiento {treatment.code}",
        body=(
            f"Hola {participant.user.full_name},\n\n"
            f"Fuiste invitado al tratamiento {treatment.code}.\n"
            f"Anomalía: {anomaly.code} - {anomaly.title}\n"
            f"Rol: {participant.get_role_display()}\n"
            f"Fecha programada: {scheduled_label}\n"
            f"Lugar: {location_label}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para consultar y gestionar la invitación."
        ),
        source_type="actions.treatment",
        source_id=treatment.pk,
        actor=actor,
        category=NotificationCategory.PARTICIPATION,
        template_code="treatment_participant_invited",
        is_task=True,
        task_type=NotificationTaskType.TREATMENT_PARTICIPATION,
        action_url=f"/treatments?treatment={treatment.pk}",
        due_at=treatment.scheduled_for,
        context_data={
            "treatment_id": str(treatment.pk),
            "treatment_code": treatment.code,
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "participant_id": str(participant.pk),
            "participant_role": participant.role,
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


def notify_anomaly_closed(
    *,
    anomaly,
    actor=None,
    closure_path: str = "administrative",
    request_id: str = "",
):
    if not anomaly.reporter_id or not anomaly.closed_at:
        return None
    event_key = anomaly.closed_at.isoformat()
    if _event_notification_exists(
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        template_code=ANOMALY_CLOSED_TEMPLATE,
        event_key=event_key,
        recipient_id=anomaly.reporter_id,
    ):
        return None

    path_labels = {
        "invalid": "clasificación como inválida en la Revisión de hallazgos",
        "observation_effective": "verificación eficaz de la observación",
        "administrative": "cierre administrativo",
    }
    path_label = path_labels.get(closure_path, path_labels["administrative"])
    summary = (
        (anomaly.closure_comment or "").strip()
        or (anomaly.effectiveness_summary or "").strip()
        or (anomaly.result_summary or "").strip()
        or "La gestión de la anomalía fue finalizada."
    )
    return create_internal_notification(
        recipients=[anomaly.reporter],
        title=f"Anomalía {anomaly.code} cerrada",
        body=(
            f"Hola {anomaly.reporter.full_name},\n\n"
            f"La anomalía {anomaly.code} - {anomaly.title} fue cerrada.\n"
            f"Motivo del cierre: {path_label}.\n"
            f"Resumen de lo actuado: {summary}"
        ),
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        actor=actor,
        category=NotificationCategory.ANOMALY,
        template_code=ANOMALY_CLOSED_TEMPLATE,
        action_url=f"/anomalies/{anomaly.pk}",
        context_data={
            "event_key": event_key,
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "closure_path": closure_path,
            "closed_at": anomaly.closed_at.isoformat(),
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


def notify_treatment_closed(
    *,
    treatment,
    anomalies: list,
    newly_closed_anomalies: list,
    actor=None,
    request_id: str = "",
) -> list:
    event_at = treatment.effectiveness_validated_at or timezone.now()
    event_key = event_at.isoformat()
    notifications = []
    involved_users = _treatment_involved_users(treatment)
    involved_ids = {user.pk for user in involved_users}
    anomaly_label = ", ".join(anomaly.code for anomaly in anomalies)
    validation_comment = (treatment.effectiveness_validation_comment or "").strip() or "Resultado eficaz confirmado."

    if involved_users and not _event_notification_exists(
        source_type="actions.treatment",
        source_id=treatment.pk,
        template_code=TREATMENT_CLOSED_TEMPLATE,
        event_key=event_key,
    ):
        notifications.append(
            create_internal_notification(
                recipients=involved_users,
                title=f"Tratamiento {treatment.code} cerrado eficazmente",
                body=(
                    f"El tratamiento {treatment.code} fue validado como eficaz y quedó cerrado.\n"
                    f"Anomalía(s) cerrada(s): {anomaly_label}.\n"
                    f"Resultado de la verificación: {validation_comment}"
                ),
                source_type="actions.treatment",
                source_id=treatment.pk,
                actor=actor,
                category=NotificationCategory.INFO,
                template_code=TREATMENT_CLOSED_TEMPLATE,
                action_url=f"/treatments?treatment={treatment.pk}",
                context_data={
                    "event_key": event_key,
                    "treatment_id": str(treatment.pk),
                    "treatment_code": treatment.code,
                    "anomaly_codes": [anomaly.code for anomaly in anomalies],
                    "include_action_url_in_email": False,
                },
                request_id=request_id,
                email_enabled=True,
            )
        )

    reporter_anomalies: dict[object, tuple[object, list]] = {}
    for anomaly in newly_closed_anomalies:
        if not anomaly.reporter_id or anomaly.reporter_id in involved_ids:
            continue
        if anomaly.reporter_id not in reporter_anomalies:
            reporter_anomalies[anomaly.reporter_id] = (anomaly.reporter, [])
        reporter_anomalies[anomaly.reporter_id][1].append(anomaly)

    for reporter_id, (reporter, reported_anomalies) in reporter_anomalies.items():
        if _event_notification_exists(
            source_type="actions.treatment",
            source_id=treatment.pk,
            template_code=TREATMENT_REPORTER_CLOSURE_TEMPLATE,
            event_key=event_key,
            recipient_id=reporter_id,
        ):
            continue
        reported_label = ", ".join(
            f"{anomaly.code} - {anomaly.title}" for anomaly in reported_anomalies
        )
        notifications.append(
            create_internal_notification(
                recipients=[reporter],
                title=f"Cierre de anomalía por tratamiento eficaz {treatment.code}",
                body=(
                    f"Hola {reporter.full_name},\n\n"
                    f"La(s) anomalía(s) {reported_label} fue(ron) cerrada(s) porque el tratamiento "
                    f"{treatment.code} fue validado como eficaz.\n"
                    f"Resumen de lo actuado: {validation_comment}"
                ),
                source_type="actions.treatment",
                source_id=treatment.pk,
                actor=actor,
                category=NotificationCategory.ANOMALY,
                template_code=TREATMENT_REPORTER_CLOSURE_TEMPLATE,
                action_url=f"/treatments?treatment={treatment.pk}",
                context_data={
                    "event_key": event_key,
                    "treatment_id": str(treatment.pk),
                    "treatment_code": treatment.code,
                    "anomaly_ids": [str(anomaly.pk) for anomaly in reported_anomalies],
                    "anomaly_codes": [anomaly.code for anomaly in reported_anomalies],
                    "reporter_id": str(reporter_id),
                    "include_action_url_in_email": False,
                },
                request_id=request_id,
                email_enabled=True,
            )
        )
    return [notification for notification in notifications if notification is not None]


def notify_treatment_learned_lesson_published(*, lesson, actor=None, request_id: str = ""):
    treatment = lesson.treatment
    event_key = str(lesson.pk)
    if _event_notification_exists(
        source_type="actions.treatmentlearnedlesson",
        source_id=lesson.pk,
        template_code=TREATMENT_LEARNED_LESSON_TEMPLATE,
        event_key=event_key,
    ):
        return None
    recipients = _treatment_involved_users(treatment)
    if lesson.has_learning:
        learning_summary = (lesson.learned_text or "").strip() or "Se registró una lección aprendida."
    else:
        learning_summary = (
            (lesson.no_learning_reason or "").strip()
            or "Se registró que el tratamiento no produjo una nueva lección aprendida."
        )
    procedure_summary = (
        (lesson.procedure_modification_notes or "").strip() or "Se modificó un procedimiento."
        if lesson.procedure_modified
        else "No se registraron modificaciones de procedimiento."
    )
    return create_internal_notification(
        recipients=recipients,
        title=f"Lección aprendida publicada: {treatment.code}",
        body=(
            f"Se publicó el registro de lecciones aprendidas del tratamiento {treatment.code}.\n"
            f"Conclusión: {learning_summary}\n"
            f"Procedimientos: {procedure_summary}"
        ),
        source_type="actions.treatmentlearnedlesson",
        source_id=lesson.pk,
        actor=actor,
        category=NotificationCategory.INFO,
        template_code=TREATMENT_LEARNED_LESSON_TEMPLATE,
        action_url=f"/treatments?treatment={treatment.pk}",
        context_data={
            "event_key": event_key,
            "treatment_id": str(treatment.pk),
            "treatment_code": treatment.code,
            "lesson_id": str(lesson.pk),
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


def notify_treatment_not_effective(*, treatment, actor=None, request_id: str = ""):
    event_at = treatment.effectiveness_validated_at or timezone.now()
    event_key = event_at.isoformat()
    if _event_notification_exists(
        source_type="actions.treatment",
        source_id=treatment.pk,
        template_code=TREATMENT_NOT_EFFECTIVE_TEMPLATE,
        event_key=event_key,
    ):
        return None
    recipients = _treatment_involved_users(treatment)
    comment = (treatment.effectiveness_validation_comment or "").strip() or "La verificación resultó no eficaz."
    return create_internal_notification(
        recipients=recipients,
        title=f"Tratamiento {treatment.code}: resultado no eficaz",
        body=(
            f"La verificación de eficacia del tratamiento {treatment.code} resultó no eficaz.\n"
            f"Observación: {comment}\n"
            "El tratamiento permanece abierto y requiere revisar las acciones realizadas."
        ),
        source_type="actions.treatment",
        source_id=treatment.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        template_code=TREATMENT_NOT_EFFECTIVE_TEMPLATE,
        action_url=f"/treatments?treatment={treatment.pk}",
        context_data={
            "event_key": event_key,
            "treatment_id": str(treatment.pk),
            "treatment_code": treatment.code,
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )


def notify_observation_not_effective(
    *, anomaly, immediate_action, actor=None, request_id: str = ""
):
    event_at = immediate_action.effectiveness_verified_at or timezone.now()
    event_key = event_at.isoformat()
    if _event_notification_exists(
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        template_code=OBSERVATION_NOT_EFFECTIVE_TEMPLATE,
        event_key=event_key,
    ):
        return None
    responsible = anomaly.owner or immediate_action.responsible
    comment = (immediate_action.effectiveness_comment or "").strip() or "La verificación resultó no eficaz."
    return create_internal_notification(
        recipients=[responsible],
        title=f"Observación {anomaly.code}: resultado no eficaz",
        body=(
            f"La verificación de eficacia de la observación {anomaly.code} resultó no eficaz.\n"
            f"Observación: {comment}\n"
            "La anomalía permanece abierta y requiere registrar una nueva acción tomada."
        ),
        source_type="anomalies.anomaly",
        source_id=anomaly.pk,
        actor=actor,
        category=NotificationCategory.ACTION,
        template_code=OBSERVATION_NOT_EFFECTIVE_TEMPLATE,
        action_url=f"/anomalies/{anomaly.pk}",
        context_data={
            "event_key": event_key,
            "anomaly_id": str(anomaly.pk),
            "anomaly_code": anomaly.code,
            "include_action_url_in_email": False,
        },
        request_id=request_id,
        email_enabled=True,
    )
