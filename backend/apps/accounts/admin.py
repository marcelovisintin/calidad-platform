from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "access_level",
        "email_notifications_enabled",
        "must_change_password",
        "primary_sector",
        "is_active",
        "is_staff",
        "last_activity_at",
    )
    list_filter = (
        "access_level",
        "email_notifications_enabled",
        "must_change_password",
        "is_active",
        "is_staff",
        "is_superuser",
        "primary_sector",
    )
    search_fields = ("username", "email", "first_name", "last_name", "employee_code")
    ordering = ("username",)
    readonly_fields = (
        "date_joined",
        "last_login",
        "last_activity_at",
        "password_changed_at",
        "created_at",
        "updated_at",
    )
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Informacion corporativa",
            {
                "fields": (
                    "employee_code",
                    "photo",
                    "access_level",
                    "email_notifications_enabled",
                    "must_change_password",
                    "password_changed_at",
                    "primary_sector",
                    "last_activity_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
