import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_legacy_observation_actions(apps, schema_editor):
    AnomalyImmediateAction = apps.get_model("anomalies", "AnomalyImmediateAction")
    ObservationAction = apps.get_model("anomalies", "ObservationAction")

    legacy_actions = AnomalyImmediateAction.objects.exclude(actions_taken="").iterator()
    for legacy in legacy_actions:
        completion_date = legacy.action_completed_at or legacy.action_date
        effectiveness_date = legacy.effectiveness_due_at or completion_date
        action = ObservationAction.objects.create(
            anomaly_id=legacy.anomaly_id,
            sequence=1,
            detail=legacy.actions_taken,
            estimated_completion_date=completion_date,
            effectiveness_due_date=effectiveness_date,
            status="completed" if legacy.action_completed_at else "pending",
            completed_at=legacy.action_completed_at,
            completed_by_id=legacy.responsible_id if legacy.action_completed_at else None,
            created_by_id=legacy.created_by_id,
            updated_by_id=legacy.updated_by_id,
            row_version=legacy.row_version,
        )
        ObservationAction.objects.filter(pk=action.pk).update(
            created_at=legacy.created_at,
            updated_at=legacy.updated_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0017_alter_anomalycauseanalysis_method_used"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ObservationAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("detail", models.TextField()),
                ("estimated_completion_date", models.DateField()),
                ("effectiveness_due_date", models.DateField()),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("completed", "Finalizada")], default="pending", max_length=20)),
                ("completed_at", models.DateField(blank=True, null=True)),
                ("anomaly", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="observation_actions", to="anomalies.anomaly")),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="completed_observation_actions", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Accion de Observacion",
                "verbose_name_plural": "Acciones de Observaciones",
                "ordering": ("sequence", "created_at"),
                "indexes": [models.Index(fields=["status", "effectiveness_due_date"], name="obs_action_status_due_idx")],
                "constraints": [models.UniqueConstraint(fields=("anomaly", "sequence"), name="obs_action_anom_seq_uq")],
            },
        ),
        migrations.RunPython(migrate_legacy_observation_actions, migrations.RunPython.noop),
    ]
