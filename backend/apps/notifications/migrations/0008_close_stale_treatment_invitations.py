from django.db import migrations
from django.utils import timezone


ACTIVE_TASK_STATUSES = {"pending", "in_progress"}
FINISHED_TREATMENT_STATUSES = {"in_progress": "completed", "completed": "completed", "cancelled": "dismissed"}


def close_stale_treatment_invitations(apps, schema_editor):
    Treatment = apps.get_model("actions", "Treatment")
    Notification = apps.get_model("notifications", "Notification")
    NotificationRecipient = apps.get_model("notifications", "NotificationRecipient")

    treatment_status_by_id = dict(
        Treatment.objects.filter(status__in=FINISHED_TREATMENT_STATUSES).values_list("id", "status")
    )
    if not treatment_status_by_id:
        return

    recipients = NotificationRecipient.objects.select_related("notification").filter(
        notification__source_type="actions.treatment",
        notification__source_id__in=treatment_status_by_id,
        notification__template_code="treatment_participant_invited",
        notification__task_type="treatment_participation",
        task_status__in=ACTIVE_TASK_STATUSES,
    )
    now = timezone.now()
    notification_ids = set()
    for recipient in recipients.iterator():
        treatment_status = treatment_status_by_id.get(recipient.notification.source_id)
        recipient.task_status = FINISHED_TREATMENT_STATUSES[treatment_status]
        recipient.resolved_at = now
        update_fields = ["task_status", "resolved_at", "updated_at"]
        if recipient.channel == "email" and recipient.delivery_status == "pending":
            recipient.delivery_status = "skipped"
            recipient.delivery_error = (
                "El tratamiento fue cancelado antes del envío de la invitación."
                if treatment_status == "cancelled"
                else "El tratamiento comenzó antes del envío de la invitación."
            )
            update_fields.extend(["delivery_status", "delivery_error"])
        recipient.row_version = (recipient.row_version or 0) + 1
        update_fields.append("row_version")
        recipient.save(update_fields=update_fields)
        notification_ids.add(recipient.notification_id)

    Notification.objects.filter(id__in=notification_ids).update(status="sent", updated_at=now)


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0022_treatmentdeletionrecord"),
        ("notifications", "0007_alter_notification_task_type"),
    ]

    operations = [
        migrations.RunPython(close_stale_treatment_invitations, migrations.RunPython.noop),
    ]
