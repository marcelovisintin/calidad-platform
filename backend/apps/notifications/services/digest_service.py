from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta

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


DAILY_DUE_DIGEST_TEMPLATE = "daily_due_digest"


def _end_of_day(value):
    return timezone.make_aware(
        datetime.combine(value, time.max),
        timezone.get_current_timezone(),
    )


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
    recipients = (
        NotificationRecipient.objects.select_related("notification", "user")
        .filter(
            channel=NotificationChannel.IN_APP,
            notification__is_task=True,
            notification__due_at__isnull=False,
            notification__due_at__lte=_end_of_day(due_until),
            task_status__in=[RecipientTaskStatus.PENDING, RecipientTaskStatus.IN_PROGRESS],
            user__is_active=True,
            user__email_notifications_enabled=True,
        )
        .exclude(user__email="")
        .order_by("user_id", "notification__due_at", "notification__created_at")
    )

    grouped = defaultdict(list)
    for recipient in recipients:
        grouped[recipient.user_id].append(recipient)

    created = 0
    task_count = 0
    digest_date_value = digest_date.isoformat()
    for user_id, user_recipients in grouped.items():
        if Notification.objects.filter(
            source_type="notifications.daily_due_digest",
            source_id=user_id,
            template_code=DAILY_DUE_DIGEST_TEMPLATE,
            context_data__digest_date=digest_date_value,
        ).exists():
            continue

        overdue = []
        upcoming = []
        for recipient in user_recipients:
            due_date = timezone.localtime(recipient.notification.due_at).date()
            target = overdue if due_date < digest_date else upcoming
            target.append((recipient.notification, due_date))

        lines = [f"Hola {user_recipients[0].user.full_name},", ""]
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
        omitted = max(0, len(user_recipients) - 100)
        if omitted:
            lines.extend(["", f"Hay {omitted} pendiente(s) adicional(es) para consultar en el sistema."])
        lines.extend(["", "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para revisar tus pendientes."])

        notification = create_internal_notification(
            recipients=[user_recipients[0].user],
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
                "overdue_count": len(overdue),
                "upcoming_count": len(upcoming),
                "source_notification_ids": [
                    str(recipient.notification_id) for recipient in user_recipients
                ],
                "include_action_url_in_email": False,
            },
            email_enabled=True,
        )
        if notification:
            created += 1
            task_count += len(user_recipients)

    return {
        "enabled": True,
        "created": created,
        "users": len(grouped),
        "tasks": task_count,
    }
