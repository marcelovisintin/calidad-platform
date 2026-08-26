from django.db import migrations, models
import django.db.models.deletion


def populate_treatment_responsible(apps, schema_editor):
    Treatment = apps.get_model("actions", "Treatment")
    for treatment in Treatment.objects.select_related("primary_anomaly").iterator():
        responsible_id = treatment.primary_anomaly.owner_id
        if responsible_id:
            treatment.responsible_id = responsible_id
            treatment.save(update_fields=["responsible"])


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0010_treatment_location"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatment",
            name="responsible",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="responsible_treatments",
                to="accounts.user",
            ),
        ),
        migrations.RunPython(populate_treatment_responsible, migrations.RunPython.noop),
    ]
