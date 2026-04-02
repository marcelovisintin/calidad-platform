from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0003_alter_anomalystatushistory_from_stage_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="anomaly",
            name="affected_quantity",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="anomaly",
            name="manufacturing_order_number",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]