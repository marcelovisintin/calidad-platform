import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("anomalies", "0006_anomalyimmediateaction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AnomalyCodeReservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("year", models.PositiveIntegerField()),
                ("sequence", models.PositiveIntegerField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "anomaly",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="code_reservation",
                        to="anomalies.anomaly",
                    ),
                ),
                (
                    "consumed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="anomaly_code_reservations_consumed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="anomalycodereservation_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reserved_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="anomaly_code_reservations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="anomalycodereservation_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reserva de codigo de anomalia",
                "verbose_name_plural": "Reservas de codigos de anomalia",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="anomalycodereservation",
            constraint=models.UniqueConstraint(fields=("year", "sequence"), name="anom_code_resv_year_seq_uq"),
        ),
        migrations.AddIndex(
            model_name="anomalycodereservation",
            index=models.Index(fields=["year", "sequence"], name="anom_code_resv_year_seq_idx"),
        ),
        migrations.AddIndex(
            model_name="anomalycodereservation",
            index=models.Index(fields=["reserved_by", "consumed_at"], name="anom_code_resv_user_cons_idx"),
        ),
    ]


