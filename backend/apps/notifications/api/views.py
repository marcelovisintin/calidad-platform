from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.api.serializers import (
    NotificationInboxItemSerializer,
    NotificationInboxSummarySerializer,
    NotificationResolveSerializer,
    NotificationsApiRootSerializer,
)
from apps.notifications.selectors import (
    apply_inbox_filters,
    build_notification_recipient_queryset,
    filter_notification_recipient_queryset_for_user,
    notification_summary_for_user,
)
from apps.notifications.services import mark_notification_as_read, resolve_notification_task


class NotificationsApiRootView(APIView):
    def get(self, request):
        payload = {
            "inbox": "/api/v1/notifications/inbox/",
            "tasks": "/api/v1/notifications/inbox/tasks/",
            "summary": "/api/v1/notifications/inbox/summary/",
        }
        serializer = NotificationsApiRootSerializer(payload)
        return Response(serializer.data)


class NotificationInboxViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = filter_notification_recipient_queryset_for_user(
            build_notification_recipient_queryset(),
            self.request.user,
        )
        return apply_inbox_filters(queryset, self.request.query_params)

    def get_serializer_class(self):
        if self.action == "summary":
            return NotificationInboxSummarySerializer
        if self.action == "resolve":
            return NotificationResolveSerializer
        return NotificationInboxItemSerializer

    def _request_id(self) -> str:
        return self.request.headers.get("X-Request-ID") or self.request.headers.get("X-Request-Id") or ""

    @action(detail=False, methods=["get"], url_path="tasks")
    def tasks(self, request):
        queryset = self.get_queryset().filter(notification__is_task=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = NotificationInboxItemSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = NotificationInboxItemSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        serializer = NotificationInboxSummarySerializer(notification_summary_for_user(request.user))
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        recipient = self.get_object()
        updated = mark_notification_as_read(recipient=recipient, user=request.user, request_id=self._request_id())
        serializer = NotificationInboxItemSerializer(updated, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        recipient = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = resolve_notification_task(
            recipient=recipient,
            user=request.user,
            request_id=self._request_id(),
            **serializer.validated_data,
        )
        output = NotificationInboxItemSerializer(updated, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)
