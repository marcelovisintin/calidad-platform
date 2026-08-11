from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_user_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_notifications_enabled",
            field=models.BooleanField(default=False, verbose_name="Notificación por correo"),
        ),
    ]
