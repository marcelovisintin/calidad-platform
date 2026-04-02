import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("El username es obligatorio.")
        if not email:
            raise ValueError("El email es obligatorio.")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("access_level", User.AccessLevel.USUARIO_ACTIVO)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("access_level", User.AccessLevel.DESARROLLADOR)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    class AccessLevel(models.TextChoices):
        USUARIO_ACTIVO = "usuario_activo", "Usuario activo"
        MANDO_MEDIO_ACTIVO = "mando_medio_activo", "Mando medio activo"
        ADMINISTRADOR = "administrador", "Administrador"
        DESARROLLADOR = "desarrollador", "Desarrollador"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    employee_code = models.CharField(max_length=50, blank=True)
    access_level = models.CharField(
        max_length=30,
        choices=AccessLevel.choices,
        default=AccessLevel.USUARIO_ACTIVO,
    )
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    primary_sector = models.ForeignKey(
        "catalog.Area",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ("username",)
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def full_name(self) -> str:
        return self.get_full_name() or self.username
