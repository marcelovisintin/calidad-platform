from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("actions", "0012_treatmentcodesequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatment",
            name="convocation_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="treatment",
            name="convocation_confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="confirmed_treatment_convocations",
                to="accounts.user",
            ),
        ),
    ]
