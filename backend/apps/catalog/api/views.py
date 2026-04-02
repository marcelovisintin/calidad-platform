from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.api.serializers import (
    ActionTypeManagementSerializer,
    AnomalyOriginManagementSerializer,
    AnomalyTypeManagementSerializer,
    AreaManagementSerializer,
    CatalogApiRootSerializer,
    CatalogBootstrapSerializer,
    LineManagementSerializer,
    PriorityManagementSerializer,
    SeverityManagementSerializer,
    SiteManagementSerializer,
)
from apps.catalog.models import ActionType, AnomalyOrigin, AnomalyType, Area, Line, Priority, Severity, Site


class CatalogManagementPermission(BasePermission):
    message = "No tiene permisos suficientes para gestionar catalogos."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False

        return bool(
            user.is_superuser
            or user.is_staff
            or getattr(user, "access_level", "") in {"administrador", "desarrollador"}
        )


class CatalogManagementViewSet(viewsets.ModelViewSet):
    permission_classes = [CatalogManagementPermission]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    search_fields = ("code", "name")

    def get_queryset(self):
        queryset = super().get_queryset()

        active_value = self.request.query_params.get("active")
        if active_value is not None:
            is_active = active_value.strip().lower() in {"1", "true", "yes", "y", "on"}
            queryset = queryset.filter(is_active=is_active)

        query_text = self.request.query_params.get("q")
        if query_text:
            query_text = query_text.strip()
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": query_text})
            queryset = queryset.filter(query)

        return queryset

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError({"detail": "No se puede eliminar porque tiene registros relacionados."}) from exc


class SiteManagementViewSet(CatalogManagementViewSet):
    serializer_class = SiteManagementSerializer
    queryset = Site.objects.all().order_by("display_order", "name")
    search_fields = ("code", "name")


class AreaManagementViewSet(CatalogManagementViewSet):
    serializer_class = AreaManagementSerializer
    queryset = Area.objects.select_related("site").order_by("site__display_order", "site__name", "display_order", "name")
    search_fields = ("code", "name", "site__code", "site__name")


class LineManagementViewSet(CatalogManagementViewSet):
    serializer_class = LineManagementSerializer
    queryset = Line.objects.select_related("area", "area__site").order_by(
        "area__site__display_order",
        "area__site__name",
        "area__display_order",
        "area__name",
        "display_order",
        "name",
    )
    search_fields = ("code", "name", "area__code", "area__name", "area__site__code", "area__site__name")


class AnomalyTypeManagementViewSet(CatalogManagementViewSet):
    serializer_class = AnomalyTypeManagementSerializer
    queryset = AnomalyType.objects.all().order_by("display_order", "name")


class AnomalyOriginManagementViewSet(CatalogManagementViewSet):
    serializer_class = AnomalyOriginManagementSerializer
    queryset = AnomalyOrigin.objects.all().order_by("display_order", "name")


class SeverityManagementViewSet(CatalogManagementViewSet):
    serializer_class = SeverityManagementSerializer
    queryset = Severity.objects.all().order_by("display_order", "name")


class PriorityManagementViewSet(CatalogManagementViewSet):
    serializer_class = PriorityManagementSerializer
    queryset = Priority.objects.all().order_by("display_order", "name")


class ActionTypeManagementViewSet(CatalogManagementViewSet):
    serializer_class = ActionTypeManagementSerializer
    queryset = ActionType.objects.all().order_by("display_order", "name")


class CatalogApiRootView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = CatalogApiRootSerializer(
            {
                "bootstrap": "/api/v1/catalog/bootstrap/",
                "management": {
                    "sites": "/api/v1/catalog/sites/",
                    "areas": "/api/v1/catalog/areas/",
                    "lines": "/api/v1/catalog/lines/",
                    "anomaly_types": "/api/v1/catalog/anomaly-types/",
                    "anomaly_origins": "/api/v1/catalog/anomaly-origins/",
                    "severities": "/api/v1/catalog/severities/",
                    "priorities": "/api/v1/catalog/priorities/",
                    "action_types": "/api/v1/catalog/action-types/",
                },
            }
        )
        return Response(serializer.data)


class CatalogBootstrapAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        payload = {
            "source": "api-database",
            "generatedAt": timezone.now(),
            "sites": list(Site.objects.filter(is_active=True).order_by("display_order", "name")),
            "areas": list(
                Area.objects.filter(is_active=True)
                .select_related("site")
                .order_by("site__display_order", "site__name", "display_order", "name")
            ),
            "anomalyTypes": list(AnomalyType.objects.filter(is_active=True).order_by("display_order", "name")),
            "anomalyOrigins": list(AnomalyOrigin.objects.filter(is_active=True).order_by("display_order", "name")),
            "severities": list(Severity.objects.filter(is_active=True).order_by("display_order", "name")),
            "priorities": list(Priority.objects.filter(is_active=True).order_by("display_order", "name")),
            "actionTypes": list(ActionType.objects.filter(is_active=True).order_by("display_order", "name")),
        }
        serializer = CatalogBootstrapSerializer(payload)
        return Response(serializer.data)
