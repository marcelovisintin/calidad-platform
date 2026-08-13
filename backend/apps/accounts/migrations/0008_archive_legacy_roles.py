from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_user_email_notifications_enabled"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="UserRoleScope"),
                migrations.DeleteModel(name="Role"),
            ],
        ),
    ]
