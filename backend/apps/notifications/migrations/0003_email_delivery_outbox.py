from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_internal_tasks_and_inbox"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationrecipient",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="delivery_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="delivery_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="destination",
            field=models.CharField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="last_delivery_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="notificationrecipient",
            name="delivery_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendiente"),
                    ("processing", "Procesando"),
                    ("delivered", "Entregada"),
                    ("read", "Leida"),
                    ("failed", "Fallida"),
                    ("skipped", "Omitida"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="notificationrecipient",
            index=models.Index(
                fields=["channel", "delivery_status", "last_delivery_attempt_at"],
                name="noti_email_outbox_idx",
            ),
        ),
    ]
