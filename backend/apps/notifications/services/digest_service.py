from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationRecipient,
    RecipientTaskStatus,
)
from apps.notifications.services.notification_service import create_internal_notification
from apps.notifications.services.due_eligibility import current_due_date
from apps.anomalies.models import ObservationAction


DAILY_DUE_DIGEST_TEMPLATE = "daily_due_digest"


def refresh_due_digest_email(email_recipient) -> bool:
    """Rebuild queued content after assignments or statuses change."""
    from apps.notifications.services.email_template_catalog import render_email_template

    notification = email_recipient.notification
    original = NotificationRecipient.objects.select_related("notification").filter(
        user_id=email_recipient.user_id,
        channel=NotificationChannel.IN_APP,
        notification_id__in=notification.context_data.get("source_notification_ids", []),
    )
    today = timezone.localdate()
    due_until = today + timedelta(days=notification.context_data.get("reminder_days", settings.EMAIL_DUE_REMINDER_DAYS))
    entries = []
    for recipient in original:
        due_date = current_due_date(recipient)
        if due_date and due_date <= due_until:
            entries.append((recipient.notification, due_date))
    if not entries:
        return False

    entries.sort(key=lambda entry: entry[1])
    overdue = [(item, due) for item, due in entries if due < today]
    upcoming = [(item, due) for item, due in entries if due >= today]
    lines = []
    if overdue:
        lines.append(f"Pendientes vencidos ({len(overdue)}):")
        lines.extend(f"- {due:%d/%m/%Y}: {item.title}" for item, due in overdue[:50])
    if upcoming:
        if overdue:
            lines.append("")
        lines.append(f"Pendientes próximos a vencer ({len(upcoming)}):")
        lines.extend(f"- {due:%d/%m/%Y}: {item.title}" for item, due in upcoming[:50])
    if len(entries) > 100:
        lines.extend(["", f"Hay {len(entries) - 100} pendiente(s) adicional(es) para consultar en el sistema."])
    details = "\n".join(lines)
    title = f"Resumen de pendientes: {len(overdue)} vencido(s) y {len(upcoming)} próximo(s)"
    body = (
        f"Hola {email_recipient.user.full_name},\n\n{details}\n\n"
        "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para revisar tus pendientes."
    )
    subject, email_body = render_email_template(
        code=DAILY_DUE_DIGEST_TEMPLATE,
        context={"recipient_name": email_recipient.user.full_name,
                 "overdue_count": len(overdue), "upcoming_count": len(upcoming),
                 "pending_details": details},
        fallback_subject=title,
        fallback_body=body,
    )
    email_recipient.email_subject = subject
    email_recipient.email_body = email_body
    NotificationRecipient.objects.filter(pk=email_recipient.pk).update(email_subject=subject, email_body=email_body)
    notification.title = title
    notification.body = body
    notification.context_data = {
        **notification.context_data,
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "source_notification_ids": [str(item.pk) for item, _ in entries],
    }
    Notification.objects.filter(pk=notification.pk).update(
        title=title, body=body, context_data=notification.context_data,
    )
    return True


@transaction.atomic
def create_due_notification_digests(*, digest_date=None, reminder_days: int | None = None) -> dict[str, int | bool]:
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return {"enabled": False, "created": 0, "users": 0, "tasks": 0}

    digest_date = digest_date or timezone.localdate()
    reminder_days = (
        settings.EMAIL_DUE_REMINDER_DAYS
        if reminder_days is None
        else max(0, reminder_days)
    )
    due_until = digest_date + timedelta(days=reminder_days)
    from apps.notifications.services.notification_service import notify_observation_action_assigned

    for action in ObservationAction.objects.select_related("anomaly", "anomaly__immediate_action").filter(
        status="pending", estimated_completion_date__lte=due_until,
    ).exclude(anomaly__current_status__in=["closed", "cancelled"]):
        notify_observation_action_assigned(action=action)

    recipients = (
        NotificationRecipient.objects.select_related("notification", "user")
        .filter(
            channel=NotificationChannel.IN_APP,
            notification__is_task=True,
            task_status=RecipientTaskStatus.PENDING,
            user__is_active=True,
            user__email_notifications_enabled=True,
        )
        .exclude(user__email="")
        .order_by("user_id", "notification__due_at", "notification__created_at")
    )

    grouped = defaultdict(list)
    for recipient in recipients:
        due_date = current_due_date(recipient)
        if due_date and due_date <= due_until:
            grouped[recipient.user_id].append((recipient, due_date))

    created = 0
    task_count = 0
    digest_date_value = digest_date.isoformat()
    for user_id, entries in grouped.items():
        if Notification.objects.filter(
            source_type="notifications.daily_due_digest",
            source_id=user_id,
            template_code=DAILY_DUE_DIGEST_TEMPLATE,
            context_data__digest_date=digest_date_value,
        ).exists():
            continue

        overdue = []
        upcoming = []
        for recipient, due_date in entries:
            target = overdue if due_date < digest_date else upcoming
            target.append((recipient.notification, due_date))

        user = entries[0][0].user
        lines = [f"Hola {user.full_name},", ""]
        if overdue:
            lines.append(f"Pendientes vencidos ({len(overdue)}):")
            lines.extend(
                f"- {due_date.strftime('%d/%m/%Y')}: {notification.title}"
                for notification, due_date in overdue[:50]
            )
        if upcoming:
            if overdue:
                lines.append("")
            lines.append(f"Pendientes próximos a vencer ({len(upcoming)}):")
            lines.extend(
                f"- {due_date.strftime('%d/%m/%Y')}: {notification.title}"
                for notification, due_date in upcoming[:50]
            )
        omitted = max(0, len(entries) - 100)
        if omitted:
            lines.extend(["", f"Hay {omitted} pendiente(s) adicional(es) para consultar en el sistema."])
        pending_details = "\n".join(lines[2:])
        lines.extend(["", "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para revisar tus pendientes."])

        notification = create_internal_notification(
            recipients=[user],
            title=(
                f"Resumen de pendientes: {len(overdue)} vencido(s) y "
                f"{len(upcoming)} próximo(s)"
            ),
            body="\n".join(lines),
            source_type="notifications.daily_due_digest",
            source_id=user_id,
            category=NotificationCategory.ACTION,
            template_code=DAILY_DUE_DIGEST_TEMPLATE,
            action_url="/actions/mine",
            context_data={
                "digest_date": digest_date_value,
                "reminder_days": reminder_days,
                "overdue_count": len(overdue),
                "upcoming_count": len(upcoming),
                "source_notification_ids": [
                    str(recipient.notification_id) for recipient, _ in entries
                ],
                "include_action_url_in_email": False,
            },
            email_enabled=True,
            email_template_code=DAILY_DUE_DIGEST_TEMPLATE,
            email_context={
                "recipient_name": user.full_name,
                "overdue_count": len(overdue),
                "upcoming_count": len(upcoming),
                "pending_details": pending_details,
            },
        )
        if notification:
            created += 1
            task_count += len(entries)

    return {
        "enabled": True,
        "created": created,
        "users": len(grouped),
        "tasks": task_count,
    }
