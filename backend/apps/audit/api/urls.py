from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.audit.api.views import AuditApiRootView, AuditEventViewSet

app_name = "audit"

router = DefaultRouter()
router.register("events", AuditEventViewSet, basename="audit-event")

urlpatterns = [
    path("", AuditApiRootView.as_view(), name="audit-root"),
    path("", include(router.urls)),
]
