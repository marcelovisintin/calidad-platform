from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.actions.api.treatment_views import (
    TreatmentEvidenceDownloadAPIView,
    TreatmentLearnedLessonEvidenceDownloadAPIView,
    TreatmentLearnedLessonViewSet,
    TreatmentTaskEvidenceDownloadAPIView,
    TreatmentTrackingViewSet,
    TreatmentViewSet,
)
from apps.actions.api.views import ActionEvidenceDownloadAPIView, ActionItemViewSet, ActionPlanViewSet, ActionsApiRootView, DashboardSummaryAPIView
from apps.actions.api.work_item_views import ActionWorkItemListAPIView
from apps.actions.api.validation_item_views import ValidationItemListAPIView

app_name = "actions"

router = DefaultRouter()
router.register("plans", ActionPlanViewSet, basename="action-plan")
router.register("items", ActionItemViewSet, basename="action-item")
router.register("treatments", TreatmentViewSet, basename="treatment")
router.register("treatment-tracking", TreatmentTrackingViewSet, basename="treatment-tracking")
router.register("learned-lessons", TreatmentLearnedLessonViewSet, basename="learned-lesson")

urlpatterns = [
    path("", ActionsApiRootView.as_view(), name="actions-root"),
    path("dashboard-summary/", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("work-items/", ActionWorkItemListAPIView.as_view(), name="work-item-list"),
    path("validation-items/", ValidationItemListAPIView.as_view(), name="validation-item-list"),
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
    path(
        "learned-lessons/evidences/<uuid:evidence_id>/download/",
        TreatmentLearnedLessonEvidenceDownloadAPIView.as_view(),
        name="treatment-learned-lesson-evidence-download",
    ),
    path("", include(router.urls)),
]
