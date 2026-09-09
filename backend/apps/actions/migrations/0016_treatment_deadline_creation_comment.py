from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0015_treatmentlearnedlessonrevision"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatment",
            name="deadline",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="treatment",
            name="creation_comment",
            field=models.TextField(blank=True, default=""),
        ),
    ]
