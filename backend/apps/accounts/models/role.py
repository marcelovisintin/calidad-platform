from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import AuditBaseModel


class Role(AuditBaseModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="business_roles")

    class Meta:
        ordering = ("name",)
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class UserRoleScope(AuditBaseModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="role_scopes")
    role = models.ForeignKey("accounts.Role", on_delete=models.PROTECT, related_name="user_scopes")
    site = models.ForeignKey("catalog.Site", on_delete=models.PROTECT, related_name="user_role_scopes")
    area = models.ForeignKey(
        "catalog.Area",
        on_delete=models.PROTECT,
        related_name="user_role_scopes",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Alcance de rol"
        verbose_name_plural = "Alcances de rol"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "site", "area"],
                condition=models.Q(area__isnull=False),
                name="acc_usr_role_site_area_uq",
            ),
            models.UniqueConstraint(
                fields=["user", "role", "site"],
                condition=models.Q(area__isnull=True),
                name="acc_usr_role_site_uq",
            ),
        ]

    def clean(self):
        if self.area_id and self.area and self.area.site_id != self.site_id:
            raise ValidationError({"area": "El area seleccionada no pertenece al sitio indicado."})

    def __str__(self) -> str:
        area_name = self.area.name if self.area else "Todas las areas"
        return f"{self.user} | {self.role.name} | {self.site.name} | {area_name}"
