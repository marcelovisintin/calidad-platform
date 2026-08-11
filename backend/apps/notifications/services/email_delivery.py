from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.notifications.models import (
    DeliveryStatus,
    Notification,
    NotificationChannel,
    NotificationRecipient,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


def _absolute_action_url(action_url: str) -> str:
    value = (action_url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(f"{settings.APP_PUBLIC_URL.rstrip('/')}/", value.lstrip("/"))


def _email_body(recipient: NotificationRecipient) -> str:
    notification = recipient.notification
    parts = [notification.body.strip()]
    if action_url := _absolute_action_url(notification.action_url):
        parts.extend(["", f"Abrir en el sistema: {action_url}"])
    parts.extend(["", "Este es un mensaje automático del Sistema de Gestión de Calidad."])
    return "\n".join(parts).strip()


def _refresh_notification_status(notification_id) -> None:
    email_statuses = list(
        NotificationRecipient.objects.filter(
            notification_id=notification_id,
            channel=NotificationChannel.EMAIL,
        ).values_list("delivery_status", flat=True)
    )
    if not email_statuses:
        status = NotificationStatus.SENT
    elif any(value in {DeliveryStatus.PENDING, DeliveryStatus.PROCESSING} for value in email_statuses):
        status = NotificationStatus.PENDING
    elif any(value == DeliveryStatus.FAILED for value in email_statuses):
        status = NotificationStatus.FAILED
    else:
        status = NotificationStatus.SENT
    Notification.objects.filter(pk=notification_id).update(
        status=status,
        row_version=F("row_version") + 1,
        updated_at=timezone.now(),
    )


@transaction.atomic
def _claim_email_recipients(limit: int) -> list:
    now = timezone.now()
    retry_before = now - timedelta(minutes=settings.EMAIL_RETRY_DELAY_MINUTES)
    processing_before = now - timedelta(minutes=settings.EMAIL_PROCESSING_TIMEOUT_MINUTES)
    retryable = (
        Q(delivery_status=DeliveryStatus.PENDING)
        | Q(
            delivery_status=DeliveryStatus.FAILED,
            delivery_attempts__lt=settings.EMAIL_MAX_RETRIES,
        )
        & (Q(last_delivery_attempt_at__isnull=True) | Q(last_delivery_attempt_at__lte=retry_before))
        | Q(
            delivery_status=DeliveryStatus.PROCESSING,
            delivery_attempts__lt=settings.EMAIL_MAX_RETRIES,
            last_delivery_attempt_at__lte=processing_before,
        )
    )
    recipients = list(
        NotificationRecipient.objects.select_for_update(skip_locked=True)
        .filter(channel=NotificationChannel.EMAIL)
        .filter(retryable)
        .order_by("created_at")[:limit]
    )
    for recipient in recipients:
        recipient.delivery_status = DeliveryStatus.PROCESSING
        recipient.delivery_attempts += 1
        recipient.last_delivery_attempt_at = now
        recipient.delivery_error = ""
        recipient.row_version = (recipient.row_version or 0) + 1
        recipient.updated_at = now
    NotificationRecipient.objects.bulk_update(
        recipients,
        [
            "delivery_status",
            "delivery_attempts",
            "last_delivery_attempt_at",
            "delivery_error",
            "row_version",
            "updated_at",
        ],
    )
    return [recipient.pk for recipient in recipients]


def _mark_skipped(recipient: NotificationRecipient, reason: str) -> None:
    now = timezone.now()
    NotificationRecipient.objects.filter(pk=recipient.pk).update(
        delivery_status=DeliveryStatus.SKIPPED,
        delivery_error=reason,
        row_version=F("row_version") + 1,
        updated_at=now,
    )
    _refresh_notification_status(recipient.notification_id)


def _send_claimed_recipient(recipient_id) -> str:
    recipient = NotificationRecipient.objects.select_related("notification", "user").get(pk=recipient_id)
    if recipient.delivery_status != DeliveryStatus.PROCESSING:
        return "skipped"
    if not recipient.user.is_active:
        _mark_skipped(recipient, "Usuario inactivo al momento del envío.")
        return "skipped"
    if not recipient.user.email_notifications_enabled:
        _mark_skipped(recipient, "El usuario desactivó las notificaciones por correo.")
        return "skipped"
    if not recipient.destination:
        _mark_skipped(recipient, "El destinatario no tiene una dirección de correo.")
        return "skipped"

    try:
        message = EmailMultiAlternatives(
            subject=recipient.notification.title.replace("\r", " ").replace("\n", " "),
            body=_email_body(recipient),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.destination],
        )
        message.send(fail_silently=False)
    except Exception as exc:  # El error SMTP no debe afectar la operación de negocio.
        error_message = str(exc)[:2000] or exc.__class__.__name__
        NotificationRecipient.objects.filter(pk=recipient.pk).update(
            delivery_status=DeliveryStatus.FAILED,
            delivery_error=error_message,
            row_version=F("row_version") + 1,
            updated_at=timezone.now(),
        )
        _refresh_notification_status(recipient.notification_id)
        logger.exception("Fallo el envio de la notificacion por correo %s.", recipient.pk)
        return "failed"

    now = timezone.now()
    NotificationRecipient.objects.filter(pk=recipient.pk).update(
        delivery_status=DeliveryStatus.DELIVERED,
        delivered_at=now,
        delivery_error="",
        row_version=F("row_version") + 1,
        updated_at=now,
    )
    _refresh_notification_status(recipient.notification_id)
    return "delivered"


def dispatch_pending_email_notifications(*, limit: int = 100) -> dict[str, int | bool]:
    result: dict[str, int | bool] = {
        "enabled": settings.EMAIL_NOTIFICATIONS_ENABLED,
        "claimed": 0,
        "delivered": 0,
        "failed": 0,
        "skipped": 0,
    }
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return result

    recipient_ids = _claim_email_recipients(max(1, limit))
    result["claimed"] = len(recipient_ids)
    for recipient_id in recipient_ids:
        outcome = _send_claimed_recipient(recipient_id)
        result[outcome] = int(result[outcome]) + 1
    return result
