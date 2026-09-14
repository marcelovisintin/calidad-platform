from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0017_rename_treatment_task_codes_to_actions"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="treatmenttask",
            options={
                "ordering": ("created_at",),
                "verbose_name": "Accion de tratamiento",
                "verbose_name_plural": "Acciones de tratamiento",
            },
        ),
        migrations.AlterModelOptions(
            name="treatmenttaskanomaly",
            options={
                "verbose_name": "Anomalia vinculada a accion",
                "verbose_name_plural": "Anomalias vinculadas a acciones",
            },
        ),
        migrations.AlterModelOptions(
            name="treatmenttaskevidence",
            options={
                "ordering": ("-created_at",),
                "verbose_name": "Evidencia de accion de tratamiento",
                "verbose_name_plural": "Evidencias de acciones de tratamiento",
            },
        ),
    ]
