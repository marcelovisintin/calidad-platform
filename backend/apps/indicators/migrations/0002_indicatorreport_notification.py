from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("indicators", "0001_initial"),
        ("notifications", "0004_notification_finding_management_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="indicatorreport",
            name="notification",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="indicator_report",
                to="notifications.notification",
            ),
        ),
    ]
