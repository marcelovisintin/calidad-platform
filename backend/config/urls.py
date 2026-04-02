from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path



def api_root(_request):
    return JsonResponse(
        {
            "service": settings.APP_SLUG,
            "version": settings.API_VERSION,
            "status": "ok",
            "endpoints": {
                "health": f"/api/{settings.API_VERSION}/core/health/",
                "accounts": f"/api/{settings.API_VERSION}/accounts/",
                "catalog": f"/api/{settings.API_VERSION}/catalog/",
                "anomalies": f"/api/{settings.API_VERSION}/anomalies/",
                "actions": f"/api/{settings.API_VERSION}/actions/",
                "notifications": f"/api/{settings.API_VERSION}/notifications/",
                "audit": f"/api/{settings.API_VERSION}/audit/",
            },
        }
    )


api_patterns = [
    path("", api_root, name="api-root"),
    path("core/", include("apps.core.api.urls")),
    path("accounts/", include("apps.accounts.api.urls")),
    path("catalog/", include("apps.catalog.api.urls")),
    path("anomalies/", include("apps.anomalies.api.urls")),
    path("actions/", include("apps.actions.api.urls")),
    path("notifications/", include("apps.notifications.api.urls")),
    path("audit/", include("apps.audit.api.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path(f"api/{settings.API_VERSION}/", include((api_patterns, "api"), namespace="api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
