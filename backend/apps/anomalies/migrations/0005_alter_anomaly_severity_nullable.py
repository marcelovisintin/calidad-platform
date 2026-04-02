from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("anomalies", "0004_anomaly_of_and_quantity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anomaly",
            name="severity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="anomalies",
                to="catalog.severity",
            ),
        ),
    ]
