import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_legacy_orders(apps, schema_editor):
    Anomaly = apps.get_model("anomalies", "Anomaly")
    AffectedOrder = apps.get_model("anomalies", "AffectedOrder")
    OrderType = apps.get_model("catalog", "OrderType")
    order_type = OrderType.objects.filter(code__iexact="OF").first()
    if order_type is None:
        return

    for anomaly in Anomaly.objects.exclude(manufacturing_order_number="").iterator():
        number = (anomaly.manufacturing_order_number or "").strip()
        if not number:
            continue
        AffectedOrder.objects.get_or_create(
            anomaly_id=anomaly.pk,
            order_type_id=order_type.pk,
            number=number,
            defaults={
                "quantity": anomaly.affected_quantity or 1,
                "created_by_id": anomaly.created_by_id,
                "updated_by_id": anomaly.updated_by_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0007_ordertype"),
        ("anomalies", "0014_observation_action_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AffectedOrder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("number", models.CharField(max_length=50)),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                (
                    "anomaly",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affected_orders",
                        to="anomalies.anomaly",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="affected_orders",
                        to="catalog.ordertype",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Orden afectada",
                "verbose_name_plural": "Ordenes afectadas",
                "ordering": ("order_type__display_order", "order_type__name", "number"),
                "indexes": [
                    models.Index(fields=["order_type", "number"], name="aff_order_type_number_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("anomaly", "order_type", "number"),
                        name="aff_order_unique_per_anomaly",
                    ),
                ],
            },
        ),
        migrations.RunPython(migrate_legacy_orders, migrations.RunPython.noop),
    ]
