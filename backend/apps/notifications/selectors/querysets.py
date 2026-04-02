from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import NotificationRecipient, RecipientTaskStatus

OPEN_TASK_STATUSES = {
    RecipientTaskStatus.PENDING,
    RecipientTaskStatus.IN_PROGRESS,
}


def build_notification_recipient_queryset():
    return NotificationRecipient.objects.select_related(
        "notification",
        "user",
        "notification__created_by",
        "notification__updated_by",
    )


def filter_notification_recipient_queryset_for_user(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()
    return queryset.filter(user=user)


def apply_inbox_filters(queryset, params):
    if category := params.get("category"):
        queryset = queryset.filter(notification__category=category)

    if delivery_status := params.get("delivery_status"):
        queryset = queryset.filter(delivery_status=delivery_status)

    if task_status := params.get("task_status"):
        if task_status == "open":
            queryset = queryset.filter(notification__is_task=True, task_status__in=OPEN_TASK_STATUSES)
        else:
            queryset = queryset.filter(task_status=task_status)

    if is_task := params.get("is_task"):
        normalized = is_task.lower()
        if normalized in {"1", "true", "yes"}:
            queryset = queryset.filter(notification__is_task=True)
        elif normalized in {"0", "false", "no"}:
            queryset = queryset.filter(notification__is_task=False)

    if unread := params.get("unread"):
        normalized = unread.lower()
        if normalized in {"1", "true", "yes"}:
            queryset = queryset.filter(read_at__isnull=True)
        elif normalized in {"0", "false", "no"}:
            queryset = queryset.filter(read_at__isnull=False)

    if overdue := params.get("overdue"):
        normalized = overdue.lower()
        if normalized in {"1", "true", "yes"}:
            queryset = queryset.filter(notification__due_at__lt=timezone.now(), task_status__in=OPEN_TASK_STATUSES)

    if source_type := params.get("source_type"):
        queryset = queryset.filter(notification__source_type=source_type)

    if search := params.get("search"):
        queryset = queryset.filter(
            Q(notification__title__icontains=search)
            | Q(notification__body__icontains=search)
            | Q(notification__template_code__icontains=search)
        )

    return queryset


def notification_summary_for_user(user) -> dict:
    queryset = filter_notification_recipient_queryset_for_user(build_notification_recipient_queryset(), user)
    now = timezone.now()
    return {
        "total": queryset.count(),
        "unread": queryset.filter(read_at__isnull=True).count(),
        "tasks_total": queryset.filter(notification__is_task=True).count(),
        "tasks_pending": queryset.filter(task_status=RecipientTaskStatus.PENDING).count(),
        "tasks_in_progress": queryset.filter(task_status=RecipientTaskStatus.IN_PROGRESS).count(),
        "tasks_overdue": queryset.filter(notification__due_at__lt=now, task_status__in=OPEN_TASK_STATUSES).count(),
    }
