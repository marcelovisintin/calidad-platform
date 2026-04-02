from django.db import migrations


ACTION_TYPES = [
    ("CONT", "Accion de Contencion", 10),
    ("CORR", "Accion Correctiva", 20),
    ("PREV", "Accion Preventiva", 30),
    ("MEJ", "Accion de Mejora", 40),
]


def seed_action_types(apps, schema_editor):
    ActionType = apps.get_model("catalog", "ActionType")
    db_alias = schema_editor.connection.alias

    for code, name, display_order in ACTION_TYPES:
        ActionType.objects.using(db_alias).update_or_create(
            code=code,
            defaults={
                "name": name,
                "is_active": True,
                "display_order": display_order,
            },
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_action_types, noop_reverse),
    ]
