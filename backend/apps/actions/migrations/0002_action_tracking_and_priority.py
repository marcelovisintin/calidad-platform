from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def _build_action_code(anomaly_code, sequence, suffix=0):
    base = f"ACT-{anomaly_code}-{int(sequence or 1):02d}"[:80]
    if suffix:
        extra = f"-{suffix}"
        return f"{base[: 80 - len(extra)]}{extra}"
    return base


def forwards_populate_action_items(apps, schema_editor):
    ActionItem = apps.get_model("actions", "ActionItem")
    ActionItemHistory = apps.get_model("actions", "ActionItemHistory")
    db_alias = schema_editor.connection.alias

    queryset = (
        ActionItem.objects.using(db_alias)
        .select_related("action_plan__anomaly")
        .order_by("action_plan_id", "sequence", "created_at")
    )

    for item in queryset:
        updates = {}
        anomaly = item.action_plan.anomaly
        anomaly_code = getattr(anomaly, "code", "ANOM") or "ANOM"

        if not item.code:
            suffix = 0
            candidate = _build_action_code(anomaly_code, item.sequence, suffix)
            while (
                ActionItem.objects.using(db_alias)
                .filter(code=candidate)
                .exclude(pk=item.pk)
                .exists()
            ):
                suffix += 1
                candidate = _build_action_code(anomaly_code, item.sequence, suffix)
            updates["code"] = candidate
            item.code = candidate

        if not item.priority_id and getattr(anomaly, "priority_id", None):
            updates["priority_id"] = anomaly.priority_id
            item.priority_id = anomaly.priority_id

        if updates:
            ActionItem.objects.using(db_alias).filter(pk=item.pk).update(**updates)

        if not ActionItemHistory.objects.using(db_alias).filter(
            action_item_id=item.pk,
            event_type="created",
        ).exists():
            ActionItemHistory.objects.using(db_alias).create(
                action_item_id=item.pk,
                event_type="created",
                from_status="",
                to_status=item.status or "pending",
                comment="Historial inicial generado por migracion.",
                changed_by_id=item.created_by_id or item.updated_by_id,
                changed_at=item.created_at,
                snapshot_data={
                    "id": str(item.pk),
                    "action_plan_id": str(item.action_plan_id),
                    "code": item.code,
                    "status": item.status,
                    "due_date": item.due_date.isoformat() if item.due_date else "",
                    "assigned_to_id": str(item.assigned_to_id) if item.assigned_to_id else "",
                    "priority_id": str(item.priority_id) if item.priority_id else "",
                },
                created_by_id=item.created_by_id,
                updated_by_id=item.updated_by_id,
            )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("actions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionitem",
            name="code",
            field=models.CharField(blank=True, default="", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="actionitem",
            name="priority",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_items", to="catalog.priority"),
        ),
        migrations.AddField(
            model_name="actionitem",
            name="expected_evidence",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="actionitem",
            name="closure_comment",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="ActionItemHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("row_version", models.PositiveIntegerField(default=1)),
                ("event_type", models.CharField(choices=[("created", "Creada"), ("updated", "Actualizada"), ("reassigned", "Reasignada"), ("status_changed", "Cambio de estado"), ("evidence_added", "Evidencia agregada")], max_length=30)),
                ("from_status", models.CharField(blank=True, default="", max_length=20)),
                ("to_status", models.CharField(blank=True, default="", max_length=20)),
                ("comment", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField()),
                ("snapshot_data", models.JSONField(blank=True, default=dict)),
                ("action_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="actions.actionitem")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_item_history_entries", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Historial de accion",
                "verbose_name_plural": "Historial de acciones",
                "ordering": ("-changed_at", "-created_at"),
            },
        ),
        migrations.RunPython(forwards_populate_action_items, noop_reverse),
        migrations.AddIndex(
            model_name="actionitem",
            index=models.Index(fields=["assigned_to", "due_date"], name="act_item_asg_due_idx"),
        ),
        migrations.AddConstraint(
            model_name="actionitem",
            constraint=models.UniqueConstraint(condition=~models.Q(code=""), fields=("code",), name="act_item_code_uq"),
        ),
        migrations.AddIndex(
            model_name="actionitemhistory",
            index=models.Index(fields=["action_item", "changed_at"], name="act_hist_item_changed_idx"),
        ),
    ]
