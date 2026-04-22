from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.actions.api.treatment_views import (
    TreatmentEvidenceDownloadAPIView,
    TreatmentTaskEvidenceDownloadAPIView,
    TreatmentViewSet,
)
from apps.actions.api.views import ActionEvidenceDownloadAPIView, ActionItemViewSet, ActionPlanViewSet, ActionsApiRootView

app_name = "actions"

router = DefaultRouter()
router.register("plans", ActionPlanViewSet, basename="action-plan")
router.register("items", ActionItemViewSet, basename="action-item")
router.register("treatments", TreatmentViewSet, basename="treatment")

urlpatterns = [
    path("", ActionsApiRootView.as_view(), name="actions-root"),
    path("evidences/<uuid:evidence_id>/download/", ActionEvidenceDownloadAPIView.as_view(), name="evidence-download"),
    path(
        "treatments/evidences/<uuid:evidence_id>/download/",
        TreatmentEvidenceDownloadAPIView.as_view(),
        name="treatment-evidence-download",
    ),
    path(
        "treatments/task-evidences/<uuid:evidence_id>/download/",
        TreatmentTaskEvidenceDownloadAPIView.as_view(),
        name="treatment-task-evidence-download",
    ),
    path("", include(router.urls)),
]
