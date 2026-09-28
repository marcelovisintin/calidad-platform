from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0020_treatment_analysis_methods"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatmentparticipant",
            name="added_after_convocation",
            field=models.BooleanField(default=False),
        ),
    ]
