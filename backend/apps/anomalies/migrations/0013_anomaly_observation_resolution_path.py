from django.db import migrations, models
from django.db.models import Q


def backfill_observation_resolution_path(apps, schema_editor):
    Anomaly = apps.get_model("anomalies", "Anomaly")
    AnomalyImmediateAction = apps.get_model("anomalies", "AnomalyImmediateAction")
    Treatment = apps.get_model("actions", "Treatment")
    TreatmentAnomaly = apps.get_model("actions", "TreatmentAnomaly")

    immediate_action_ids = AnomalyImmediateAction.objects.values("anomaly_id")
    Anomaly.objects.filter(id__in=immediate_action_ids).update(observation_resolution_path="OBSERVATION")

    legacy_observation_label = "accion " + "inmediata"
    observation_q = (
        Q(severity__name__icontains="Observacion")
        | Q(severity__code__icontains="Observacion")
        | Q(severity__name__icontains="inmediata")
        | Q(severity__code__icontains="inmediata")
        | Q(classification_summary__icontains="Observacion")
        | Q(classification_summary__icontains=legacy_observation_label)
        | Q(classification__summary__icontains="Observacion")
        | Q(classification__summary__icontains=legacy_observation_label)
    )
    treatment_anomaly_ids = TreatmentAnomaly.objects.values("anomaly_id")
    primary_treatment_anomaly_ids = Treatment.objects.values("primary_anomaly_id")
    Anomaly.objects.filter(observation_q, observation_resolution_path__isnull=True).filter(
        Q(id__in=treatment_anomaly_ids) | Q(id__in=primary_treatment_anomaly_ids)
    ).update(observation_resolution_path="TREATMENT")


class Migration(migrations.Migration):

    dependencies = [
        ("actions", "0010_treatment_location"),
        ("anomalies", "0012_immediate_action_effectiveness_result"),
    ]

    operations = [
        migrations.AddField(
            model_name="anomaly",
            name="observation_resolution_path",
            field=models.CharField(
                blank=True,
                choices=[
                    ("OBSERVATION", "Observacion"),
                    ("TREATMENT", "Tratamiento"),
                ],
                db_index=True,
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_observation_resolution_path, migrations.RunPython.noop),
    ]
