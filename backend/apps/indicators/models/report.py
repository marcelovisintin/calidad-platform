from django.db import models

from apps.core.models import AuditBaseModel
from common.storage import indicator_report_upload_to


class IndicatorReportStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    READY = "ready", "Generado"
    QUEUED = "queued", "Encolado"
    COMPLETED = "completed", "Completado"
    FAILED = "failed", "Fallido"


class IndicatorReport(AuditBaseModel):
    indicator_key = models.SlugField(max_length=80)
    period_from = models.DateField()
    period_to = models.DateField()
    filters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=IndicatorReportStatus.choices,
        default=IndicatorReportStatus.PENDING,
    )
    row_count = models.PositiveIntegerField(default=0)
    report_file = models.FileField(upload_to=indicator_report_upload_to, null=True, blank=True)
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="application/pdf")
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    notification = models.OneToOneField(
        "notifications.Notification",
        on_delete=models.SET_NULL,
        related_name="indicator_report",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Informe de indicador"
        verbose_name_plural = "Informes de indicadores"
        indexes = [
            models.Index(fields=["indicator_key", "period_from", "period_to"], name="ind_report_period_idx"),
            models.Index(fields=["status", "created_at"], name="ind_report_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.indicator_key}: {self.period_from} - {self.period_to}"
