from django.urls import path

from apps.indicators.api.views import (
    IndicatorCsvView,
    IndicatorDashboardView,
    IndicatorReportCreateView,
    IndicatorReportDetailView,
    IndicatorReportRecipientsView,
    IndicatorsApiRootView,
)


app_name = "indicators"

urlpatterns = [
    path("", IndicatorsApiRootView.as_view(), name="root"),
    path("report-recipients/", IndicatorReportRecipientsView.as_view(), name="report-recipients"),
    path("reports/<uuid:report_id>/", IndicatorReportDetailView.as_view(), name="report-detail"),
    path("<slug:key>/csv/", IndicatorCsvView.as_view(), name="csv"),
    path("<slug:key>/reports/", IndicatorReportCreateView.as_view(), name="report-create"),
    path("<slug:key>/", IndicatorDashboardView.as_view(), name="dashboard"),
]
