from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("anomalies", "0020_history_document_snapshot")]

    operations = [
        migrations.AddField(
            model_name="anomalyattachment", name="note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="anomalyattachment", name="observation_action",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="evidences", to="anomalies.observationaction",
            ),
        ),
    ]
