from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0013_anomaly_observation_resolution_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="anomalyimmediateaction",
            name="action_completed_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="anomalyimmediateaction",
            name="effectiveness_due_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="anomalyimmediateaction",
            name="actions_taken",
            field=models.TextField(blank=True, default=""),
        ),
    ]
