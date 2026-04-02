from django.urls import path

from apps.core.api.views import HealthCheckAPIView

app_name = "core"

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="health"),
]
