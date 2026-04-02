from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.catalog.api.views import (
    ActionTypeManagementViewSet,
    AnomalyOriginManagementViewSet,
    AnomalyTypeManagementViewSet,
    AreaManagementViewSet,
    CatalogApiRootView,
    CatalogBootstrapAPIView,
    LineManagementViewSet,
    PriorityManagementViewSet,
    SeverityManagementViewSet,
    SiteManagementViewSet,
)

app_name = "catalog"

router = DefaultRouter()
router.register("sites", SiteManagementViewSet, basename="catalog-site")
router.register("areas", AreaManagementViewSet, basename="catalog-area")
router.register("lines", LineManagementViewSet, basename="catalog-line")
router.register("anomaly-types", AnomalyTypeManagementViewSet, basename="catalog-anomaly-type")
router.register("anomaly-origins", AnomalyOriginManagementViewSet, basename="catalog-anomaly-origin")
router.register("severities", SeverityManagementViewSet, basename="catalog-severity")
router.register("priorities", PriorityManagementViewSet, basename="catalog-priority")
router.register("action-types", ActionTypeManagementViewSet, basename="catalog-action-type")

urlpatterns = [
    path("", CatalogApiRootView.as_view(), name="catalog-root"),
    path("bootstrap/", CatalogBootstrapAPIView.as_view(), name="catalog-bootstrap"),
] + router.urls
