from django.db import models
from django.utils import timezone

from apps.core.models import AuditBaseModel
from common.storage import treatment_evidence_upload_to, treatment_task_evidence_upload_to


class TreatmentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    SCHEDULED = "scheduled", "Programado"
    IN_PROGRESS = "in_progress", "En tratamiento"
    COMPLETED = "completed", "Completado"
    CANCELLED = "cancelled", "Cancelado"


class TreatmentMethod(models.TextChoices):
    FIVE_WHYS = "five_whys", "5 Why"
    SIX_M = "6m", "6M"
    ISHIKAWA = "ishikawa", "Ishikawa"
    A3 = "a3", "A3"
    EIGHT_D = "8d", "8D"
    OTHER = "other", "Otro"


class TreatmentParticipantRole(models.TextChoices):
    CONVOKED = "convoked", "Convocado"
    FACILITATOR = "facilitator", "Facilitador"
    OWNER = "owner", "Responsable"


class TreatmentTaskStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    IN_PROGRESS = "in_progress", "En curso"
    COMPLETED = "completed", "Completada"
    CANCELLED = "cancelled", "Cancelada"


class Treatment(AuditBaseModel):
    code = models.CharField(max_length=40, unique=True)
    primary_anomaly = models.ForeignKey(
        "anomalies.Anomaly",
        on_delete=models.PROTECT,
        related_name="primary_treatments",
    )
    status = models.CharField(max_length=20, choices=TreatmentStatus.choices, default=TreatmentStatus.PENDING)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    method_used = models.CharField(max_length=20, choices=TreatmentMethod.choices, blank=True, default="")
    observations = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Tratamiento"
        verbose_name_plural = "Tratamientos"
        indexes = [
            models.Index(fields=["status", "scheduled_for"], name="trt_status_sched_idx"),
            models.Index(fields=["code"], name="trt_code_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.primary_anomaly.code}"


class TreatmentAnomaly(AuditBaseModel):
    treatment = models.ForeignKey("actions.Treatment", on_delete=models.CASCADE, related_name="anomaly_links")
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.PROTECT, related_name="treatment_links")
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Anomalia asociada a tratamiento"
        verbose_name_plural = "Anomalias asociadas a tratamientos"
        constraints = [
            models.UniqueConstraint(fields=["treatment", "anomaly"], name="trt_anom_uq"),
        ]


class TreatmentParticipant(AuditBaseModel):
    treatment = models.ForeignKey("actions.Treatment", on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="treatment_participations")
    role = models.CharField(max_length=20, choices=TreatmentParticipantRole.choices, default=TreatmentParticipantRole.CONVOKED)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "Participante de tratamiento"
        verbose_name_plural = "Participantes de tratamiento"
        constraints = [
            models.UniqueConstraint(fields=["treatment", "user"], name="trt_user_uq"),
        ]


class TreatmentRootCause(AuditBaseModel):
    treatment = models.ForeignKey("actions.Treatment", on_delete=models.CASCADE, related_name="root_causes")
    sequence = models.PositiveIntegerField(default=1)
    description = models.TextField()

    class Meta:
        ordering = ("sequence", "created_at")
        verbose_name = "Causa raiz de tratamiento"
        verbose_name_plural = "Causas raiz de tratamiento"
        constraints = [
            models.UniqueConstraint(fields=["treatment", "sequence"], name="trt_root_seq_uq"),
        ]


class TreatmentTask(AuditBaseModel):
    treatment = models.ForeignKey("actions.Treatment", on_delete=models.CASCADE, related_name="tasks")
    root_cause = models.ForeignKey(
        "actions.TreatmentRootCause",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=60, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    responsible = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="treatment_tasks",
        null=True,
        blank=True,
    )
    execution_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=TreatmentTaskStatus.choices, default=TreatmentTaskStatus.PENDING)

    class Meta:
        ordering = ("created_at",)
        verbose_name = "Tarea de tratamiento"
        verbose_name_plural = "Tareas de tratamiento"
        constraints = [
            models.UniqueConstraint(fields=["code"], condition=~models.Q(code=""), name="trt_task_code_uq"),
        ]

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.status in {TreatmentTaskStatus.PENDING, TreatmentTaskStatus.IN_PROGRESS}
            and self.execution_date
            and self.execution_date < timezone.localdate()
        )


class TreatmentTaskAnomaly(AuditBaseModel):
    task = models.ForeignKey("actions.TreatmentTask", on_delete=models.CASCADE, related_name="anomaly_links")
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.PROTECT, related_name="treatment_task_links")

    class Meta:
        verbose_name = "Anomalia vinculada a tarea"
        verbose_name_plural = "Anomalias vinculadas a tareas"
        constraints = [
            models.UniqueConstraint(fields=["task", "anomaly"], name="trt_task_anom_uq"),
        ]


class TreatmentEvidence(AuditBaseModel):
    treatment = models.ForeignKey("actions.Treatment", on_delete=models.CASCADE, related_name="evidences")
    file = models.FileField(upload_to=treatment_evidence_upload_to)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="treatment_evidences",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Evidencia de tratamiento"
        verbose_name_plural = "Evidencias de tratamiento"


class TreatmentTaskEvidence(AuditBaseModel):
    treatment_task = models.ForeignKey("actions.TreatmentTask", on_delete=models.CASCADE, related_name="evidences")
    file = models.FileField(upload_to=treatment_task_evidence_upload_to)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="treatment_task_evidences",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Evidencia de tarea de tratamiento"
        verbose_name_plural = "Evidencias de tareas de tratamiento"
