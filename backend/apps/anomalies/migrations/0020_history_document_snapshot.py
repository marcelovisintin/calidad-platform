from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("anomalies", "0019_observation_learned_lesson_policy")]
    operations = [
        migrations.AddField(
            model_name="anomalystatushistory", name="document_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
