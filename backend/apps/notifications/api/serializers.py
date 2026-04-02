from rest_framework import serializers

from apps.notifications.models import NotificationRecipient, RecipientTaskStatus


class NotificationsApiRootSerializer(serializers.Serializer):
    inbox = serializers.CharField()
    tasks = serializers.CharField()
    summary = serializers.CharField()


class NotificationInboxItemSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="notification.title", read_only=True)
    body = serializers.CharField(source="notification.body", read_only=True)
    category = serializers.CharField(source="notification.category", read_only=True)
    is_task = serializers.BooleanField(source="notification.is_task", read_only=True)
    task_type = serializers.CharField(source="notification.task_type", read_only=True)
    action_url = serializers.CharField(source="notification.action_url", read_only=True)
    due_at = serializers.DateTimeField(source="notification.due_at", read_only=True, allow_null=True)
    source_type = serializers.CharField(source="notification.source_type", read_only=True)
    source_id = serializers.UUIDField(source="notification.source_id", read_only=True)
    context_data = serializers.JSONField(source="notification.context_data", read_only=True)
    created_at = serializers.DateTimeField(source="notification.created_at", read_only=True)

    class Meta:
        model = NotificationRecipient
        fields = (
            "id",
            "title",
            "body",
            "category",
            "is_task",
            "task_type",
            "action_url",
            "due_at",
            "delivery_status",
            "read_at",
            "task_status",
            "assigned_at",
            "resolved_at",
            "source_type",
            "source_id",
            "context_data",
            "created_at",
        )


class NotificationInboxSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    unread = serializers.IntegerField()
    tasks_total = serializers.IntegerField()
    tasks_pending = serializers.IntegerField()
    tasks_in_progress = serializers.IntegerField()
    tasks_overdue = serializers.IntegerField()


class NotificationResolveSerializer(serializers.Serializer):
    task_status = serializers.ChoiceField(
        choices=[
            RecipientTaskStatus.IN_PROGRESS,
            RecipientTaskStatus.COMPLETED,
            RecipientTaskStatus.DISMISSED,
        ]
    )
    comment = serializers.CharField(required=False, allow_blank=True)
