from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notifications.api.views import NotificationInboxViewSet, NotificationsApiRootView

app_name = "notifications"

router = DefaultRouter()
router.register("inbox", NotificationInboxViewSet, basename="notification-inbox")

urlpatterns = [
    path("", NotificationsApiRootView.as_view(), name="notifications-root"),
    path("", include(router.urls)),
]
