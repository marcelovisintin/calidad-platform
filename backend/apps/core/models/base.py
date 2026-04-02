import uuid

from django.conf import settings
from django.db import models


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDPrimaryKeyModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True


class AuditBaseModel(TimeStampedModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_updated",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class ActiveCatalogModel(TimeStampedModel):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ("display_order", "name")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
