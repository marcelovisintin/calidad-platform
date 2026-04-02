from django.contrib import admin

from apps.catalog.models import ActionType, AnomalyOrigin, AnomalyType, Area, Line, Priority, Severity, Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "site", "is_active")
    list_filter = ("is_active", "site")
    list_select_related = ("site",)
    search_fields = ("code", "name", "site__name")


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "area", "is_active")
    list_filter = ("is_active", "area")
    list_select_related = ("area", "area__site")
    search_fields = ("code", "name", "area__name")


@admin.register(AnomalyType)
@admin.register(AnomalyOrigin)
@admin.register(Severity)
@admin.register(Priority)
@admin.register(ActionType)
class CatalogLookupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("display_order", "name")
