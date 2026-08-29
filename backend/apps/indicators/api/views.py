from rest_framework.response import Response
from rest_framework.views import APIView

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from apps.indicators.api.serializers import (
    IndicatorDashboardSerializer,
    IndicatorReportRecipientSerializer,
    IndicatorReportRequestSerializer,
    IndicatorReportSerializer,
    IndicatorsApiRootSerializer,
)
from apps.indicators.catalog import indicator_catalog, indicator_definition
from apps.indicators.permissions import CanViewIndicators
from apps.indicators.models import IndicatorReport
from apps.indicators.reports import build_csv_response, create_and_queue_report, eligible_report_recipients
from apps.indicators.services import build_indicator_dashboard
from common.permissions import IsAuthenticatedAndActive


def _report_payload(report):
    recipients = [
        {
            "id": item.user_id,
            "name": item.user.full_name,
            "email": item.destination,
            "delivery_status": item.delivery_status,
            "delivery_error": item.delivery_error,
        }
        for item in report.notification.recipients.select_related("user").all()
    ] if report.notification_id else []
    return {
        "id": report.pk,
        "indicator_key": report.indicator_key,
        "status": report.status,
        "row_count": report.row_count,
        "filename": report.original_name,
        "checksum_sha256": report.checksum_sha256,
        "generated_at": report.generated_at,
        "expires_at": report.expires_at,
        "recipients": recipients,
    }


def _creator_report_or_403(request, report_id):
    report = get_object_or_404(IndicatorReport.objects.select_related("notification"), pk=report_id)
    if report.created_by_id != request.user.pk:
        raise PermissionDenied("Solo el usuario que genero el informe puede consultar esta copia.")
    return report


class IndicatorsApiRootView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewIndicators]

    def get(self, request):
        payload = {
            "indicators": [
                {
                    **item,
                    "dashboard_url": f"/indicators/{item['key']}",
                }
                for item in indicator_catalog()
            ]
        }
        return Response(IndicatorsApiRootSerializer(payload).data)


class IndicatorDashboardView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewIndicators]

    def get(self, request, key: str):
        definition = indicator_definition(key)
        if definition is None:
            raise Http404
        payload = build_indicator_dashboard(key, request.query_params)
        if payload is None:
            return Response({**definition, "available": False})
        return Response(IndicatorDashboardSerializer(payload).data)


class IndicatorCsvView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewIndicators]

    def get(self, request, key: str):
        if indicator_definition(key) is None:
            raise Http404
        return build_csv_response(key, request.query_params, generated_by=request.user)


class IndicatorReportRecipientsView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewIndicators]

    def get(self, request):
        payload = [
            {"id": user.pk, "name": user.full_name, "email": user.email}
            for user in eligible_report_recipients()
        ]
        return Response(IndicatorReportRecipientSerializer(payload, many=True).data)


class IndicatorReportCreateView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewIndicators]

    def post(self, request, key: str):
        if indicator_definition(key) is None:
            raise Http404
        serializer = IndicatorReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        params = {
            name: value.isoformat() if hasattr(value, "isoformat") else str(value)
            for name, value in data.items()
            if name != "recipient_ids" and value not in (None, "")
        }
        report = create_and_queue_report(
            key=key,
            params=params,
            recipient_ids=data["recipient_ids"],
            actor=request.user,
        )
        return Response(IndicatorReportSerializer(_report_payload(report)).data, status=201)


class IndicatorReportDetailView(APIView):
    permission_classes = [IsAuthenticatedAndActive, CanViewIndicators]

    def get(self, request, report_id):
        report = _creator_report_or_403(request, report_id)
        return Response(IndicatorReportSerializer(_report_payload(report)).data)
