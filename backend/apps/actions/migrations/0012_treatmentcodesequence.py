from django.db import migrations, models


def initialize_treatment_sequences(apps, schema_editor):
    Treatment = apps.get_model("actions", "Treatment")
    TreatmentCodeSequence = apps.get_model("actions", "TreatmentCodeSequence")
    maxima = {}
    for code in Treatment.objects.filter(code__startswith="TRT-").values_list("code", flat=True):
        parts = code.split("-")
        if len(parts) != 3:
            continue
        try:
            year = int(parts[1])
            sequence = int(parts[2])
        except (TypeError, ValueError):
            continue
        maxima[year] = max(maxima.get(year, 0), sequence)

    for year, sequence in maxima.items():
        TreatmentCodeSequence.objects.update_or_create(
            year=year,
            defaults={"last_sequence": sequence},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0011_treatment_responsible"),
    ]

    operations = [
        migrations.CreateModel(
            name="TreatmentCodeSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(unique=True)),
                ("last_sequence", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Secuencia de codigo de tratamiento",
                "verbose_name_plural": "Secuencias de codigos de tratamiento",
                "ordering": ("-year",),
            },
        ),
        migrations.RunPython(initialize_treatment_sequences, migrations.RunPython.noop),
    ]
