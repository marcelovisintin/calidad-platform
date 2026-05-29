import common.storage
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="photo",
            field=models.FileField(blank=True, null=True, upload_to=common.storage.user_photo_upload_to),
        ),
    ]
