from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("actions", "0013_treatment_convocation_confirmation")]

    operations = [
        migrations.AddField(
            model_name="treatmenttask",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
