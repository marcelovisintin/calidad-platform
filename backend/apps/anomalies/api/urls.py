from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.anomalies.api.views import AnomalyAttachmentDownloadAPIView, AnomalyViewSet, AnomalyWorkflowMetadataAPIView

app_name = "anomalies"

router = DefaultRouter()
router.register("", AnomalyViewSet, basename="anomaly")

urlpatterns = [
    path("workflow-metadata/", AnomalyWorkflowMetadataAPIView.as_view(), name="workflow-metadata"),
    path("attachments/<uuid:attachment_id>/download/", AnomalyAttachmentDownloadAPIView.as_view(), name="attachment-download"),
    path("", include(router.urls)),
]
