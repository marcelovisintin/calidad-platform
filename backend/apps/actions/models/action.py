from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import AuditBaseModel
from common.storage import action_evidence_upload_to


class ActionPlanStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    ACTIVE = "active", "Activo"
    COMPLETED = "completed", "Completado"
    CANCELLED = "cancelled", "Cancelado"


class ActionItemStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    IN_PROGRESS = "in_progress", "En curso"
    COMPLETED = "completed", "Completada"
    CANCELLED = "cancelled", "Cancelada"


class ActionHistoryEvent(models.TextChoices):
    CREATED = "created", "Creada"
    UPDATED = "updated", "Actualizada"
    REASSIGNED = "reassigned", "Reasignada"
    STATUS_CHANGED = "status_changed", "Cambio de estado"
    EVIDENCE_ADDED = "evidence_added", "Evidencia agregada"


class ActionPlan(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="action_plans")
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="owned_action_plans",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=ActionPlanStatus.choices, default=ActionPlanStatus.DRAFT)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Plan de accion"
        verbose_name_plural = "Planes de accion"
        constraints = [
            models.UniqueConstraint(
                fields=["anomaly"],
                condition=models.Q(status=ActionPlanStatus.ACTIVE),
                name="act_active_plan_anom_uq",
            )
        ]

    def __str__(self) -> str:
        return f"Plan {self.anomaly.code} ({self.status})"


class ActionItem(AuditBaseModel):
    action_plan = models.ForeignKey("actions.ActionPlan", on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=80, blank=True)
    action_type = models.ForeignKey("catalog.ActionType", on_delete=models.PROTECT, related_name="action_items")
    priority = models.ForeignKey(
        "catalog.Priority",
        on_delete=models.PROTECT,
        related_name="action_items",
        null=True,
        blank=True,
    )
    assigned_to = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="action_items",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ActionItemStatus.choices, default=ActionItemStatus.PENDING)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=1)
    expected_evidence = models.TextField(blank=True)
    closure_comment = models.TextField(blank=True)

    class Meta:
        ordering = ("sequence", "created_at")
        verbose_name = "Accion"
        verbose_name_plural = "Acciones"
        constraints = [
            models.UniqueConstraint(fields=["action_plan", "sequence"], name="act_plan_seq_uq"),
            models.UniqueConstraint(fields=["code"], condition=~models.Q(code=""), name="act_item_code_uq"),
        ]
        indexes = [
            models.Index(fields=["status", "due_date", "assigned_to"], name="act_status_due_asg_idx"),
            models.Index(fields=["assigned_to", "due_date"], name="act_item_asg_due_idx"),
        ]

    def clean(self):
        if self.completed_at and self.status != ActionItemStatus.COMPLETED:
            raise ValidationError({"completed_at": "completed_at solo puede informarse cuando el estado es completed."})

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.status in {ActionItemStatus.PENDING, ActionItemStatus.IN_PROGRESS}
            and self.due_date
            and self.due_date < timezone.localdate()
        )

    @property
    def effective_status(self) -> str:
        return "overdue" if self.is_overdue else self.status

    def __str__(self) -> str:
        return f"{self.code or self.action_plan.anomaly.code} - {self.title}"


class ActionItemHistory(AuditBaseModel):
    action_item = models.ForeignKey("actions.ActionItem", on_delete=models.CASCADE, related_name="history")
    event_type = models.CharField(max_length=30, choices=ActionHistoryEvent.choices)
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20, blank=True, default="")
    comment = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="action_item_history_entries",
        null=True,
        blank=True,
    )
    changed_at = models.DateTimeField()
    snapshot_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-changed_at", "-created_at")
        verbose_name = "Historial de accion"
        verbose_name_plural = "Historial de acciones"
        indexes = [models.Index(fields=["action_item", "changed_at"], name="act_hist_item_changed_idx")]


class ActionEvidence(AuditBaseModel):
    action_item = models.ForeignKey("actions.ActionItem", on_delete=models.CASCADE, related_name="evidences")
    evidence_type = models.CharField(max_length=50, default="file")
    file = models.FileField(upload_to=action_evidence_upload_to, null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Evidencia de accion"
        verbose_name_plural = "Evidencias de accion"
