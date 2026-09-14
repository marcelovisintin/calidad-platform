from django.db import migrations


def _rename_codes(apps, *, source_marker, target_marker):
    TreatmentTask = apps.get_model("actions", "TreatmentTask")
    for task in TreatmentTask.objects.select_related("treatment").exclude(code="").iterator():
        prefix = f"{task.treatment.code}-{source_marker}"
        if not task.code.startswith(prefix):
            continue
        sequence = task.code[len(prefix):]
        if not sequence.isdigit():
            continue
        target_code = f"{task.treatment.code}-{target_marker}{sequence}"
        if TreatmentTask.objects.exclude(pk=task.pk).filter(code=target_code).exists():
            raise RuntimeError(
                f"No se puede renombrar {task.code} a {target_code}: el codigo ya existe."
            )
        TreatmentTask.objects.filter(pk=task.pk).update(code=target_code)


def rename_task_codes_to_actions(apps, schema_editor):
    _rename_codes(apps, source_marker="T", target_marker="A")


def rename_action_codes_to_tasks(apps, schema_editor):
    _rename_codes(apps, source_marker="A", target_marker="T")


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0016_treatment_deadline_creation_comment"),
    ]

    operations = [
        migrations.RunPython(
            rename_task_codes_to_actions,
            rename_action_codes_to_tasks,
        ),
    ]
