from django.db import migrations, models


def seed_invalid_severity_flags(apps, schema_editor):
    Severity = apps.get_model("catalog", "Severity")
    invalid_terms = ("invalida", "invalid")

    for severity in Severity.objects.all():
        haystack = f"{severity.code or ''} {severity.name or ''}".lower()
        normalized = (
            haystack.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ü", "u")
        )
        if any(term in normalized for term in invalid_terms):
            severity.closes_anomaly_as_invalid = True
            severity.requires_classification_responsible = False
            severity.save(
                update_fields=[
                    "closes_anomaly_as_invalid",
                    "requires_classification_responsible",
                    "updated_at",
                ]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_rename_origin_priority_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="severity",
            name="closes_anomaly_as_invalid",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="severity",
            name="requires_classification_responsible",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(seed_invalid_severity_flags, migrations.RunPython.noop),
    ]
