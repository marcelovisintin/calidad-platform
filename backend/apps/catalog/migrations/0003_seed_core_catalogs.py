from django.db import migrations


SITES = [
    ("001", "corte", 10),
    ("P01", "Area 1", 20),
]

AREAS = [
    ("001", "001", "corte", 10),
    ("P01", "A01", "Area 1", 10),
]

ANOMALY_TYPES = [
    ("001", "rayado", 10),
    ("002", "faltante de material", 20),
]

ANOMALY_ORIGINS = [
    ("o01", "proceso", 10),
]

SEVERITIES = [
    ("alta", "Alta", 10),
    ("baja", "Baja", 20),
]

PRIORITIES = [
    ("alta", "Prioridad Alta", 10),
    ("baja", "Prioridad Baja", 20),
]


def seed_core_catalogs(apps, schema_editor):
    Site = apps.get_model("catalog", "Site")
    Area = apps.get_model("catalog", "Area")
    AnomalyType = apps.get_model("catalog", "AnomalyType")
    AnomalyOrigin = apps.get_model("catalog", "AnomalyOrigin")
    Severity = apps.get_model("catalog", "Severity")
    Priority = apps.get_model("catalog", "Priority")
    db_alias = schema_editor.connection.alias

    site_map = {}
    for code, name, display_order in SITES:
        site, _ = Site.objects.using(db_alias).update_or_create(
            code=code,
            defaults={
                "name": name,
                "is_active": True,
                "display_order": display_order,
            },
        )
        site_map[code] = site

    for site_code, code, name, display_order in AREAS:
        Area.objects.using(db_alias).update_or_create(
            site=site_map[site_code],
            code=code,
            defaults={
                "name": name,
                "is_active": True,
                "display_order": display_order,
            },
        )

    for model, rows in (
        (AnomalyType, ANOMALY_TYPES),
        (AnomalyOrigin, ANOMALY_ORIGINS),
        (Severity, SEVERITIES),
        (Priority, PRIORITIES),
    ):
        for code, name, display_order in rows:
            model.objects.using(db_alias).update_or_create(
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
        ("catalog", "0002_seed_action_types"),
    ]

    operations = [
        migrations.RunPython(seed_core_catalogs, noop_reverse),
    ]
