from rest_framework import serializers


class IndicatorDefinitionSerializer(serializers.Serializer):
    key = serializers.SlugField()
    sequence = serializers.IntegerField(min_value=1)
    title = serializers.CharField()
    description = serializers.CharField()
    primary_date = serializers.CharField()
    dashboard_url = serializers.CharField()


class IndicatorsApiRootSerializer(serializers.Serializer):
    indicators = IndicatorDefinitionSerializer(many=True)


class IndicatorMetricSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.IntegerField()
    percentage = serializers.FloatField(allow_null=True)
    tone = serializers.CharField()
    hint = serializers.CharField(required=False)
    comparison = serializers.JSONField(allow_null=True)


class IndicatorDashboardSerializer(serializers.Serializer):
    key = serializers.SlugField()
    sequence = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    primary_date = serializers.CharField()
    available = serializers.BooleanField()
    period = serializers.JSONField()
    filters = serializers.JSONField()
    formula_notes = serializers.ListField(child=serializers.CharField())
    metrics = IndicatorMetricSerializer(many=True)
    series = serializers.JSONField()
    breakdown = serializers.JSONField()
    rows = serializers.JSONField()


class IndicatorReportRecipientSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    delivery_status = serializers.CharField(required=False)
    delivery_error = serializers.CharField(required=False, allow_blank=True)


class IndicatorReportRequestSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    area = serializers.UUIDField(required=False, allow_null=True)
    group_by = serializers.CharField(required=False, allow_blank=True)
    recipient_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class IndicatorReportSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    indicator_key = serializers.CharField()
    status = serializers.CharField()
    row_count = serializers.IntegerField()
    filename = serializers.CharField()
    checksum_sha256 = serializers.CharField()
    generated_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    recipients = IndicatorReportRecipientSerializer(many=True)
