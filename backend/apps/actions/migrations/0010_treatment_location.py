from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("actions", "0009_treatment_learned_lesson"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatment",
            name="treatment_location",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
