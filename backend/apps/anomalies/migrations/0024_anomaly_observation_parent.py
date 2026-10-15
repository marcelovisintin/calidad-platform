from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("anomalies", "0023_optional_observation_action_file")]

    operations = [
        migrations.AddField(
            model_name="anomaly", name="observation_parent",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="associated_observation_anomalies", to="anomalies.anomaly"),
        ),
        migrations.AddConstraint(
            model_name="anomaly",
            constraint=models.CheckConstraint(condition=~models.Q(observation_parent=models.F("id")),
                                              name="anomaly_observation_not_self"),
        ),
    ]
