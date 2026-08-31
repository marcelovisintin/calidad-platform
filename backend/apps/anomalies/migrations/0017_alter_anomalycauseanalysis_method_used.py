from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0016_alter_anomaly_observation_resolution_path"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anomalycauseanalysis",
            name="method_used",
            field=models.CharField(
                choices=[
                    ("five_whys", "5 Why"),
                    ("6m", "6M"),
                    ("ishikawa", "Ishikawa"),
                    ("a3", "A3"),
                    ("8d", "8D"),
                    ("pdca", "PDCA"),
                    ("other", "Otro"),
                ],
                max_length=30,
            ),
        ),
    ]
