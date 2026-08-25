import uuid

from django.db import migrations, models


def seed_order_types(apps, schema_editor):
    OrderType = apps.get_model("catalog", "OrderType")
    defaults = (
        ("3e607440-b5ee-4f08-9ad0-fcd14e734001", "OP", "Orden de produccion", 10),
        ("3e607440-b5ee-4f08-9ad0-fcd14e734002", "OF", "Orden de fabricacion", 20),
        ("3e607440-b5ee-4f08-9ad0-fcd14e734003", "OM", "Orden de mantenimiento", 30),
    )
    for item_id, code, name, display_order in defaults:
        item, _ = OrderType.objects.get_or_create(
            code=code,
            defaults={
                "id": uuid.UUID(item_id),
                "name": name,
                "display_order": display_order,
                "is_active": True,
            },
        )
        item.name = name
        item.display_order = display_order
        item.is_active = True
        item.save(update_fields=["name", "display_order", "is_active", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_severity_classification_flow_flags"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderType",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=150)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Tipo de orden afectada",
                "verbose_name_plural": "Tipos de ordenes afectadas",
                "ordering": ("display_order", "name"),
                "constraints": [
                    models.UniqueConstraint(fields=("code",), name="catalog_unique_order_type_code"),
                ],
            },
        ),
        migrations.RunPython(seed_order_types, migrations.RunPython.noop),
    ]
