from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_notification_finding_management_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationrecipient",
            name="email_body",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="notificationrecipient",
            name="email_subject",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
