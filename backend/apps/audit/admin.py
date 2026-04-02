import json

from django.contrib import admin
from django.utils.html import format_html

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entity_type", "entity_id", "action", "actor", "request_id")
    list_filter = ("entity_type", "action", "created_at")
    list_select_related = ("actor",)
    search_fields = (
        "entity_type",
        "action",
        "request_id",
        "entity_id",
        "actor__username",
        "actor__email",
    )
    date_hierarchy = "created_at"
    readonly_fields = (
        "entity_type",
        "entity_id",
        "action",
        "actor",
        "request_id",
        "created_at",
        "formatted_before_data",
        "formatted_after_data",
    )
    fieldsets = (
        (
            "Evento",
            {
                "fields": ("entity_type", "entity_id", "action", "actor", "request_id", "created_at"),
            },
        ),
        (
            "Payload",
            {
                "fields": ("formatted_before_data", "formatted_after_data"),
            },
        ),
    )

    def _format_json(self, value):
        pretty = json.dumps(value or {}, indent=2, ensure_ascii=False, sort_keys=True)
        return format_html("<pre style='white-space: pre-wrap; margin: 0;'>{}</pre>", pretty)

    def formatted_before_data(self, obj):
        return self._format_json(getattr(obj, "before_data", {}))

    formatted_before_data.short_description = "Datos previos"

    def formatted_after_data(self, obj):
        return self._format_json(getattr(obj, "after_data", {}))

    formatted_after_data.short_description = "Datos posteriores"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return False
