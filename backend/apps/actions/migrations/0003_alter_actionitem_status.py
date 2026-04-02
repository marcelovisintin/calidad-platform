from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("actions", "0002_action_tracking_and_priority"),
    ]

    operations = [
        migrations.AlterField(
            model_name="actionitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendiente"),
                    ("in_progress", "En curso"),
                    ("completed", "Completada"),
                    ("cancelled", "Cancelada"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
