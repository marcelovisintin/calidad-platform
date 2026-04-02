from django.db import models

from apps.core.models import UUIDPrimaryKeyModel


class AuditEvent(UUIDPrimaryKeyModel):
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=100)
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    request_id = models.CharField(max_length=100, blank=True)
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Evento de auditoria"
        verbose_name_plural = "Eventos de auditoria"
        indexes = [models.Index(fields=["entity_type", "entity_id", "created_at"], name="audit_entity_idx")]

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.action}"
