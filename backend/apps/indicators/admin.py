from django.contrib import admin

from apps.indicators.models import IndicatorReport


@admin.register(IndicatorReport)
class IndicatorReportAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "indicator_key",
        "period_from",
        "period_to",
        "status",
        "row_count",
        "created_by",
    )
    list_filter = ("indicator_key", "status", "created_at")
    search_fields = ("indicator_key", "original_name", "checksum_sha256", "created_by__username")
    readonly_fields = (
        "indicator_key",
        "period_from",
        "period_to",
        "filters",
        "status",
        "row_count",
        "report_file",
        "original_name",
        "content_type",
        "checksum_sha256",
        "generated_at",
        "expires_at",
        "error_message",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"}

    def has_delete_permission(self, request, obj=None):
        return False
