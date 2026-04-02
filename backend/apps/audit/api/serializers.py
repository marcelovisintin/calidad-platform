from rest_framework import serializers

from apps.audit.models import AuditEvent


class AuditApiRootSerializer(serializers.Serializer):
    events = serializers.CharField()
    summary = serializers.CharField()


class AuditActorSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class AuditEventListSerializer(serializers.ModelSerializer):
    actor = AuditActorSummarySerializer(read_only=True)
    source_app = serializers.SerializerMethodField()
    model_name = serializers.SerializerMethodField()
    has_request_id = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "entity_type",
            "source_app",
            "model_name",
            "entity_id",
            "action",
            "actor",
            "request_id",
            "has_request_id",
            "created_at",
        )

    def get_source_app(self, obj):
        return obj.entity_type.partition(".")[0]

    def get_model_name(self, obj):
        return obj.entity_type.partition(".")[2]

    def get_has_request_id(self, obj):
        return bool(obj.request_id)


class AuditEventDetailSerializer(AuditEventListSerializer):
    before_data = serializers.JSONField(read_only=True)
    after_data = serializers.JSONField(read_only=True)

    class Meta(AuditEventListSerializer.Meta):
        fields = AuditEventListSerializer.Meta.fields + (
            "before_data",
            "after_data",
        )


class AuditSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    today = serializers.IntegerField()
    with_actor = serializers.IntegerField()
    request_tracked = serializers.IntegerField()
    entity_types = serializers.IntegerField()
    action_types = serializers.IntegerField()
    latest_event_at = serializers.DateTimeField(allow_null=True)
