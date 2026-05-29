from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("anomalies", "0010_anomalystatushistory_evidence_note"),
        ("catalog", "0005_rename_origin_priority_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="anomaly",
            name="imputed_area",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="imputed_anomalies",
                to="catalog.area",
            ),
        ),
    ]
