from django.db import migrations, models

import common.storage


class Migration(migrations.Migration):
    dependencies = [
        ("anomalies", "0022_correct_observation_verifier_roles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anomalyattachment",
            name="file",
            field=models.FileField(blank=True, upload_to=common.storage.anomaly_attachment_upload_to),
        ),
        migrations.AddConstraint(
            model_name="anomalyattachment",
            constraint=models.CheckConstraint(
                condition=~models.Q(file="") | (models.Q(observation_action__isnull=False) & ~models.Q(note="")),
                name="anom_attachment_file_or_action_note",
            ),
        ),
    ]
