from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import CanViewAuditTrail
from apps.audit.api.serializers import (
    AuditApiRootSerializer,
    AuditEventDetailSerializer,
    AuditEventListSerializer,
    AuditSummarySerializer,
)
from apps.audit.selectors import apply_audit_event_filters, audit_summary_for_queryset, build_audit_event_queryset


class AuditApiRootView(APIView):
    permission_classes = [CanViewAuditTrail]

    def get(self, request):
        payload = {
            "events": "/api/v1/audit/events/",
            "summary": "/api/v1/audit/events/summary/",
        }
        serializer = AuditApiRootSerializer(payload)
        return Response(serializer.data)


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    http_method_names = ["get", "head", "options"]
    permission_classes = [CanViewAuditTrail]

    def get_queryset(self):
        queryset = build_audit_event_queryset()
        return apply_audit_event_filters(queryset, self.request.query_params)

    def get_serializer_class(self):
        if self.action == "summary":
            return AuditSummarySerializer
        if self.action == "retrieve":
            return AuditEventDetailSerializer
        return AuditEventListSerializer

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        serializer = AuditSummarySerializer(audit_summary_for_queryset(self.get_queryset()))
        return Response(serializer.data)
