from django.db import migrations
from django.utils import timezone


ACTIVE_STATUSES = {"pending", "in_progress"}
TERMINAL_STATUSES = {"completed", "dismissed"}
TREATMENT_STATUS_MAP = {
    "pending": "pending",
    "scheduled": "in_progress",
    "in_progress": "in_progress",
    "completed": "completed",
    "cancelled": "dismissed",
}


def sync_finding_management_statuses(apps, schema_editor):
    Anomaly = apps.get_model("anomalies", "Anomaly")
    AnomalyImmediateAction = apps.get_model("anomalies", "AnomalyImmediateAction")
    Treatment = apps.get_model("actions", "Treatment")
    TreatmentAnomaly = apps.get_model("actions", "TreatmentAnomaly")
    Notification = apps.get_model("notifications", "Notification")
    NotificationRecipient = apps.get_model("notifications", "NotificationRecipient")

    recipients = list(
        NotificationRecipient.objects.select_related("notification").filter(
            notification__source_type="anomalies.anomaly",
            notification__template_code="finding_management_assigned",
            notification__task_type="finding_management",
            task_status__in=ACTIVE_STATUSES,
        )
    )
    if not recipients:
        return

    anomaly_ids = {recipient.notification.source_id for recipient in recipients}
    anomaly_statuses = dict(
        Anomaly.objects.filter(pk__in=anomaly_ids).values_list("id", "current_status")
    )
    immediate_action_ids = set(
        AnomalyImmediateAction.objects.filter(anomaly_id__in=anomaly_ids).values_list("anomaly_id", flat=True)
    )
    treatment_by_anomaly = dict(
        TreatmentAnomaly.objects.filter(anomaly_id__in=anomaly_ids).values_list("anomaly_id", "treatment_id")
    )
    treatment_statuses = dict(
        Treatment.objects.filter(pk__in=treatment_by_anomaly.values()).values_list("id", "status")
    )

    now = timezone.now()
    terminal_notification_ids = set()
    for recipient in recipients:
        anomaly_id = recipient.notification.source_id
        treatment_id = treatment_by_anomaly.get(anomaly_id)
        if treatment_id:
            target_status = TREATMENT_STATUS_MAP.get(treatment_statuses.get(treatment_id), "pending")
        else:
            anomaly_status = anomaly_statuses.get(anomaly_id)
            if anomaly_status == "cancelled":
                target_status = "dismissed"
            elif anomaly_status in {"closed", "pending_verification"}:
                target_status = "completed"
            elif anomaly_status == "in_treatment" or anomaly_id in immediate_action_ids:
                target_status = "in_progress"
            else:
                target_status = "pending"

        if target_status == recipient.task_status:
            continue
        recipient.task_status = target_status
        recipient.resolved_at = now if target_status in TERMINAL_STATUSES else None
        recipient.row_version = (recipient.row_version or 0) + 1
        update_fields = ["task_status", "resolved_at", "row_version", "updated_at"]
        if (
            target_status in TERMINAL_STATUSES
            and recipient.channel == "email"
            and recipient.delivery_status == "pending"
        ):
            recipient.delivery_status = "skipped"
            recipient.delivery_error = "La gestión del hallazgo ya finalizó."
            update_fields.extend(["delivery_status", "delivery_error"])
        recipient.save(update_fields=update_fields)
        if target_status in TERMINAL_STATUSES:
            terminal_notification_ids.add(recipient.notification_id)

    Notification.objects.filter(pk__in=terminal_notification_ids).update(status="sent", updated_at=now)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0008_close_stale_treatment_invitations"),
    ]

    operations = [
        migrations.RunPython(sync_finding_management_statuses, migrations.RunPython.noop),
    ]
