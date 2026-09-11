from rest_framework import mixins, status, viewsets
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.notifications.api.serializers import (
    EmailTemplateUpdateSerializer,
    NotificationInboxItemSerializer,
    NotificationInboxSummarySerializer,
    NotificationResolveSerializer,
    NotificationsApiRootSerializer,
)
from apps.notifications.models import NotificationChannel, NotificationTemplate
from apps.notifications.selectors import (
    OPEN_TASK_STATUSES,
    apply_inbox_filters,
    build_notification_recipient_queryset,
    filter_notification_recipient_queryset_for_user,
    notification_summary_for_user,
)
from apps.notifications.services import mark_notification_as_read, resolve_notification_task
from apps.notifications.services.email_template_catalog import (
    EMAIL_TEMPLATE_BY_CODE,
    EMAIL_TEMPLATE_DEFINITIONS,
    serialize_email_template_definition,
    validate_email_template,
)


class EmailTemplateManagementPermission(BasePermission):
    message = "Solo administradores y desarrolladores pueden editar los correos."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.is_superuser or user.access_level in {"administrador", "desarrollador"})
        )


class NotificationsApiRootView(APIView):
    def get(self, request):
        payload = {
            "inbox": "/api/v1/notifications/inbox/",
            "tasks": "/api/v1/notifications/inbox/tasks/",
            "summary": "/api/v1/notifications/inbox/summary/",
            "email_templates": "/api/v1/notifications/email-templates/",
        }
        serializer = NotificationsApiRootSerializer(payload)
        return Response(serializer.data)


class EmailTemplateListView(APIView):
    permission_classes = [EmailTemplateManagementPermission]

    def get(self, request):
        overrides = {
            item.code: item
            for item in NotificationTemplate.objects.select_related("updated_by").filter(
                channel=NotificationChannel.EMAIL,
                code__in=EMAIL_TEMPLATE_BY_CODE,
                is_active=True,
            )
        }
        return Response(
            [
                serialize_email_template_definition(definition, overrides.get(definition.code))
                for definition in EMAIL_TEMPLATE_DEFINITIONS
            ]
        )


class EmailTemplateDetailView(APIView):
    permission_classes = [EmailTemplateManagementPermission]

    def _definition(self, code):
        definition = EMAIL_TEMPLATE_BY_CODE.get(code)
        if definition is None:
            return None, Response({"detail": "Caso de correo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return definition, None

    def _request_id(self, request) -> str:
        return request.headers.get("X-Request-ID") or request.headers.get("X-Request-Id") or ""

    def patch(self, request, code):
        definition, error_response = self._definition(code)
        if error_response:
            return error_response

        serializer = EmailTemplateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subject_template = serializer.validated_data["subject_template"]
        body_template = serializer.validated_data["body_template"]
        try:
            validate_email_template(
                definition=definition,
                subject_template=subject_template,
                body_template=body_template,
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            override = NotificationTemplate.objects.select_for_update().filter(code=code).first()
            requested_version = serializer.validated_data.get("row_version")
            version_supplied = "row_version" in serializer.validated_data
            version_conflict = version_supplied and (
                (override is not None and requested_version != override.row_version)
                or (override is None and requested_version is not None)
            )
            if version_conflict:
                return Response(
                    {"detail": "El correo fue modificado por otro usuario. Recargue antes de guardar."},
                    status=status.HTTP_409_CONFLICT,
                )

            before_data = {}
            if override:
                before_data = {
                    "subject_template": override.subject_template,
                    "body_template": override.body_template,
                    "row_version": override.row_version,
                }
                override.channel = NotificationChannel.EMAIL
                override.subject_template = subject_template
                override.body_template = body_template
                override.is_active = True
                override.updated_by = request.user
                override.row_version += 1
            else:
                override = NotificationTemplate(
                    code=code,
                    channel=NotificationChannel.EMAIL,
                    subject_template=subject_template,
                    body_template=body_template,
                    is_active=True,
                    created_by=request.user,
                    updated_by=request.user,
                )
            override.full_clean()
            override.save()
            record_audit_event(
                entity=override,
                action="notification.email_template_updated",
                actor=request.user,
                before_data=before_data,
                after_data={
                    "subject_template": override.subject_template,
                    "body_template": override.body_template,
                    "row_version": override.row_version,
                },
                request_id=self._request_id(request),
            )

        return Response(serialize_email_template_definition(definition, override))

    def delete(self, request, code):
        definition, error_response = self._definition(code)
        if error_response:
            return error_response

        with transaction.atomic():
            override = NotificationTemplate.objects.select_for_update().filter(
                code=code,
                channel=NotificationChannel.EMAIL,
            ).first()
            if override:
                record_audit_event(
                    entity=override,
                    action="notification.email_template_restored",
                    actor=request.user,
                    before_data={
                        "subject_template": override.subject_template,
                        "body_template": override.body_template,
                        "row_version": override.row_version,
                    },
                    after_data={"restored_to_default": True},
                    request_id=self._request_id(request),
                )
                override.delete()

        return Response(serialize_email_template_definition(definition))


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
        if not (request.query_params.get("task_status") or "").strip():
            queryset = queryset.filter(task_status__in=OPEN_TASK_STATUSES)
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
