from django.db import migrations, models
from django.db.models import Q


def add_observation_code_suffix(apps, schema_editor):
    Anomaly = apps.get_model("anomalies", "Anomaly")
    observation_q = (
        Q(severity__code__iexact="OBS")
        | Q(severity__name__icontains="Observacion")
        | Q(severity__name__icontains="Observación")
        | Q(classification_summary__icontains="Observacion")
        | Q(classification_summary__icontains="Observación")
        | Q(classification__summary__icontains="Observacion")
        | Q(classification__summary__icontains="Observación")
    )

    for anomaly in Anomaly.objects.filter(observation_q).distinct().only("id", "code"):
        if anomaly.code.upper().endswith("-OBS"):
            continue
        observation_code = f"{anomaly.code}-OBS"
        if Anomaly.objects.exclude(pk=anomaly.pk).filter(code__iexact=observation_code).exists():
            continue
        Anomaly.objects.filter(pk=anomaly.pk).update(code=observation_code)


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0015_affectedorder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anomaly",
            name="observation_resolution_path",
            field=models.CharField(
                blank=True,
                choices=[
                    ("OBSERVATION", "Observacion"),
                    ("TREATMENT_PENDING", "Observacion TRT (con tratamiento)"),
                    ("TREATMENT", "Tratamiento"),
                ],
                db_index=True,
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(add_observation_code_suffix, migrations.RunPython.noop),
    ]
