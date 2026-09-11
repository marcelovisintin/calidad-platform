from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notifications.api.views import (
    EmailTemplateDetailView,
    EmailTemplateListView,
    NotificationInboxViewSet,
    NotificationsApiRootView,
)

app_name = "notifications"

router = DefaultRouter()
router.register("inbox", NotificationInboxViewSet, basename="notification-inbox")

urlpatterns = [
    path("email-templates/", EmailTemplateListView.as_view(), name="email-template-list"),
    path("email-templates/<str:code>/", EmailTemplateDetailView.as_view(), name="email-template-detail"),
    path("", NotificationsApiRootView.as_view(), name="notifications-root"),
    path("", include(router.urls)),
]
