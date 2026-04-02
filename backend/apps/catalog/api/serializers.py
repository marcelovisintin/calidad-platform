from rest_framework import serializers

from apps.catalog.models import ActionType, AnomalyOrigin, AnomalyType, Area, Line, Priority, Severity, Site


class SiteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ("id", "code", "name")


class AreaSummarySerializer(serializers.ModelSerializer):
    site = SiteSummarySerializer(read_only=True)

    class Meta:
        model = Area
        fields = ("id", "code", "name", "site")


class LineSummarySerializer(serializers.ModelSerializer):
    area = AreaSummarySerializer(read_only=True)

    class Meta:
        model = Line
        fields = ("id", "code", "name", "area")


class CatalogSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class CatalogApiRootSerializer(serializers.Serializer):
    bootstrap = serializers.CharField()
    management = serializers.DictField(child=serializers.CharField(), required=False)


class CatalogBootstrapSerializer(serializers.Serializer):
    source = serializers.CharField()
    generatedAt = serializers.DateTimeField()
    sites = SiteSummarySerializer(many=True)
    areas = AreaSummarySerializer(many=True)
    anomalyTypes = CatalogSummarySerializer(many=True)
    anomalyOrigins = CatalogSummarySerializer(many=True)
    severities = CatalogSummarySerializer(many=True)
    priorities = CatalogSummarySerializer(many=True)
    actionTypes = CatalogSummarySerializer(many=True)


class CatalogManagementSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "id",
            "code",
            "name",
            "is_active",
            "display_order",
            "created_at",
            "updated_at",
            "row_version",
        )


class SiteManagementSerializer(CatalogManagementSerializer):
    class Meta(CatalogManagementSerializer.Meta):
        model = Site


class AreaManagementSerializer(CatalogManagementSerializer):
    site = SiteSummarySerializer(read_only=True)
    site_id = serializers.PrimaryKeyRelatedField(source="site", queryset=Site.objects.all(), write_only=True)

    class Meta(CatalogManagementSerializer.Meta):
        model = Area
        fields = CatalogManagementSerializer.Meta.fields + ("site", "site_id")


class LineManagementSerializer(CatalogManagementSerializer):
    area = AreaSummarySerializer(read_only=True)
    area_id = serializers.PrimaryKeyRelatedField(source="area", queryset=Area.objects.select_related("site"), write_only=True)

    class Meta(CatalogManagementSerializer.Meta):
        model = Line
        fields = CatalogManagementSerializer.Meta.fields + ("area", "area_id")


class AnomalyTypeManagementSerializer(CatalogManagementSerializer):
    class Meta(CatalogManagementSerializer.Meta):
        model = AnomalyType


class AnomalyOriginManagementSerializer(CatalogManagementSerializer):
    class Meta(CatalogManagementSerializer.Meta):
        model = AnomalyOrigin


class SeverityManagementSerializer(CatalogManagementSerializer):
    class Meta(CatalogManagementSerializer.Meta):
        model = Severity


class PriorityManagementSerializer(CatalogManagementSerializer):
    class Meta(CatalogManagementSerializer.Meta):
        model = Priority


class ActionTypeManagementSerializer(CatalogManagementSerializer):
    class Meta(CatalogManagementSerializer.Meta):
        model = ActionType
