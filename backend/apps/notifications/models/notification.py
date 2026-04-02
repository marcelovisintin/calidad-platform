from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import AuditBaseModel


class NotificationChannel(models.TextChoices):
    IN_APP = "in_app", "In app"
    EMAIL = "email", "Email"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    SENT = "sent", "Enviada"
    FAILED = "failed", "Fallida"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    DELIVERED = "delivered", "Entregada"
    READ = "read", "Leida"
    FAILED = "failed", "Fallida"


class NotificationCategory(models.TextChoices):
    INFO = "info", "Informacion"
    ACTION = "action", "Accion"
    PARTICIPATION = "participation", "Participacion"
    ANOMALY = "anomaly", "Anomalia"
    SYSTEM = "system", "Sistema"


class NotificationTaskType(models.TextChoices):
    NONE = "", "Sin tarea"
    ACTION_ASSIGNMENT = "action_assignment", "Asignacion de accion"
    ANALYSIS_PARTICIPATION = "analysis_participation", "Participacion en analisis"
    TREATMENT_PARTICIPATION = "treatment_participation", "Participacion en tratamiento"
    VERIFICATION_PARTICIPATION = "verification_participation", "Participacion en verificacion"


class RecipientTaskStatus(models.TextChoices):
    NONE = "none", "Sin tarea"
    PENDING = "pending", "Pendiente"
    IN_PROGRESS = "in_progress", "En curso"
    COMPLETED = "completed", "Completada"
    DISMISSED = "dismissed", "Descartada"


class NotificationTemplate(AuditBaseModel):
    code = models.CharField(max_length=50, unique=True)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "Template de notificacion"
        verbose_name_plural = "Templates de notificacion"


class Notification(AuditBaseModel):
    source_type = models.CharField(max_length=100)
    source_id = models.UUIDField()
    template_code = models.CharField(max_length=50, blank=True, default="")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=NotificationCategory.choices, default=NotificationCategory.INFO)
    is_task = models.BooleanField(default=False)
    task_type = models.CharField(max_length=40, choices=NotificationTaskType.choices, blank=True, default="")
    action_url = models.CharField(max_length=255, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.PENDING)
    context_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Notificacion"
        verbose_name_plural = "Notificaciones"
        indexes = [models.Index(fields=["source_type", "source_id"], name="noti_source_idx")]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        if self.is_task and not self.task_type:
            raise ValidationError({"task_type": "Debe informar task_type cuando la notificacion representa una tarea."})
        if not self.is_task and self.task_type:
            raise ValidationError({"task_type": "Solo corresponde informar task_type cuando is_task es verdadero."})


class NotificationRecipient(AuditBaseModel):
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="notifications")
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)
    delivery_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    read_at = models.DateTimeField(null=True, blank=True)
    task_status = models.CharField(
        max_length=20,
        choices=RecipientTaskStatus.choices,
        default=RecipientTaskStatus.NONE,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Destinatario de notificacion"
        verbose_name_plural = "Destinatarios de notificacion"
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "user", "channel"],
                name="noti_recip_chan_uq",
            )
        ]
        indexes = [
            models.Index(fields=["user", "delivery_status", "read_at"], name="notifications_user_status_idx"),
            models.Index(fields=["user", "task_status", "resolved_at"], name="notifications_user_task_idx"),
        ]

    def clean(self):
        if self.notification.is_task and self.task_status == RecipientTaskStatus.NONE:
            raise ValidationError({"task_status": "Debe informar el estado de tarea para notificaciones con tarea."})
        if not self.notification.is_task and self.task_status != RecipientTaskStatus.NONE:
            raise ValidationError({"task_status": "Solo corresponde task_status cuando la notificacion es una tarea."})
        if self.resolved_at and self.task_status not in {RecipientTaskStatus.COMPLETED, RecipientTaskStatus.DISMISSED}:
            raise ValidationError({"resolved_at": "Solo puede informar resolved_at para tareas completadas o descartadas."})
