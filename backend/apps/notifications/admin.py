from django.contrib import admin

from apps.notifications.models import Notification, NotificationRecipient, NotificationTemplate


class NotificationRecipientInline(admin.TabularInline):
    model = NotificationRecipient
    extra = 0
    fields = (
        "user",
        "channel",
        "delivery_status",
        "task_status",
        "assigned_at",
        "read_at",
        "resolved_at",
    )
    readonly_fields = fields


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "channel", "is_active")
    list_filter = ("channel", "is_active")
    search_fields = ("code", "subject_template")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_task", "task_type", "status", "due_at", "created_at")
    list_filter = ("category", "is_task", "task_type", "status")
    search_fields = ("title", "body", "template_code", "source_type")
    inlines = [NotificationRecipientInline]


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ("notification", "user", "delivery_status", "task_status", "assigned_at", "resolved_at")
    list_filter = ("channel", "delivery_status", "task_status")
    list_select_related = ("notification", "user")
    search_fields = ("user__username", "notification__title", "notification__template_code")
