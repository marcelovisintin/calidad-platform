import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill_deleted_treatments(apps, schema_editor):
    AuditEvent = apps.get_model("audit", "AuditEvent")
    Anomaly = apps.get_model("anomalies", "Anomaly")
    TreatmentDeletionRecord = apps.get_model("actions", "TreatmentDeletionRecord")

    events = AuditEvent.objects.filter(
        entity_type="actions.treatment",
        action="treatment.deleted",
        actor_id__isnull=False,
    ).order_by("created_at")
    for event in events.iterator():
        before = event.before_data or {}
        after = event.after_data or {}
        code = (before.get("code") or "").strip()
        if not code:
            continue
        primary_anomaly_id = before.get("primary_anomaly_id") or None
        if primary_anomaly_id and not Anomaly.objects.filter(pk=primary_anomaly_id).exists():
            primary_anomaly_id = None
        anomaly_ids = before.get("anomaly_ids") or []
        TreatmentDeletionRecord.objects.update_or_create(
            original_treatment_id=event.entity_id,
            defaults={
                "code": code,
                "primary_anomaly_id": primary_anomaly_id,
                "responsible_id": before.get("responsible_id") or None,
                "previous_status": before.get("status") or "pending",
                "deadline": before.get("deadline") or None,
                "creation_comment": before.get("creation_comment") or "",
                "scheduled_for": before.get("scheduled_for") or None,
                "treatment_location": before.get("treatment_location") or "",
                "convocation_confirmed_at": before.get("convocation_confirmed_at") or None,
                "treatment_created_at": event.created_at,
                "treatment_updated_at": event.created_at,
                "deleted_by_id": event.actor_id,
                "deletion_reason": after.get("deletion_reason") or "Sin fundamento registrado en la eliminación anterior.",
                "deleted_at": event.created_at,
                "participants_snapshot": [],
                "anomalies_snapshot": [{"id": str(value)} for value in anomaly_ids],
                "created_by_id": event.actor_id,
                "updated_by_id": event.actor_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0021_treatmentparticipant_added_after_convocation"),
        ("audit", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TreatmentDeletionRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("original_treatment_id", models.UUIDField(unique=True)),
                ("code", models.CharField(db_index=True, max_length=40)),
                ("previous_status", models.CharField(choices=[("pending", "Pendiente"), ("scheduled", "Programado"), ("in_progress", "En tratamiento"), ("completed", "Completado"), ("cancelled", "Cancelado")], max_length=20)),
                ("deadline", models.DateField(blank=True, null=True)),
                ("creation_comment", models.TextField(blank=True, default="")),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("treatment_location", models.CharField(blank=True, default="", max_length=200)),
                ("convocation_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("treatment_created_at", models.DateTimeField()),
                ("treatment_updated_at", models.DateTimeField()),
                ("deletion_reason", models.TextField()),
                ("deleted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("participants_snapshot", models.JSONField(blank=True, default=list)),
                ("anomalies_snapshot", models.JSONField(blank=True, default=list)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
                ("deleted_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deleted_treatment_records", to=settings.AUTH_USER_MODEL)),
                ("responsible", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_responsible_treatment_records", to=settings.AUTH_USER_MODEL)),
                ("primary_anomaly", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_treatment_records", to="anomalies.anomaly")),
            ],
            options={
                "verbose_name": "Registro de tratamiento eliminado",
                "verbose_name_plural": "Registros de tratamientos eliminados",
                "ordering": ("-deleted_at",),
                "indexes": [models.Index(fields=["deleted_at"], name="trt_del_deleted_idx")],
            },
        ),
        migrations.RunPython(backfill_deleted_treatments, migrations.RunPython.noop),
    ]
