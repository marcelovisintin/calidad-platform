from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.actions.models import (
    ActionEvidence,
    ActionItem,
    ActionItemHistory,
    ActionItemStatus,
    ActionPlan,
    ActionPlanStatus,
)
from apps.anomalies.models import Anomaly
from apps.catalog.models import ActionType, Priority

DATETIME_INPUT_STYLE = {
    "input_type": "text",
    "placeholder": "YYYY-MM-DDTHH:MM:SS-03:00",
}

DATE_INPUT_STYLE = {
    "input_type": "text",
    "placeholder": "YYYY-MM-DD",
}


class UserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class AnomalySummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    current_status = serializers.CharField(read_only=True)
    current_stage = serializers.CharField(read_only=True)


class CatalogSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class ActionEvidenceSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ActionEvidence
        fields = ("id", "evidence_type", "note", "file_url", "created_at")

    def get_file_url(self, obj):
        request = self.context.get("request")
        if not obj.file:
            return ""
        url = reverse("api:actions:evidence-download", kwargs={"evidence_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


class ActionItemHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = ActionItemHistory
        fields = (
            "id",
            "event_type",
            "from_status",
            "to_status",
            "comment",
            "changed_at",
            "changed_by",
            "snapshot_data",
        )


class ActionItemBaseSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    effective_status = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    action_type = CatalogSummarySerializer(read_only=True)
    priority = CatalogSummarySerializer(read_only=True)
    assigned_to = UserSummarySerializer(read_only=True)

    class Meta:
        model = ActionItem
        fields = (
            "id",
            "code",
            "title",
            "description",
            "status",
            "effective_status",
            "is_overdue",
            "due_date",
            "completed_at",
            "is_mandatory",
            "sequence",
            "expected_evidence",
            "closure_comment",
            "action_type",
            "priority",
            "assigned_to",
            "created_at",
            "updated_at",
            "row_version",
        )


class ActionItemListSerializer(ActionItemBaseSerializer):
    class Meta(ActionItemBaseSerializer.Meta):
        fields = ActionItemBaseSerializer.Meta.fields


class ActionItemDetailSerializer(ActionItemBaseSerializer):
    evidences = ActionEvidenceSerializer(many=True, read_only=True)
    history = ActionItemHistorySerializer(many=True, read_only=True)

    class Meta(ActionItemBaseSerializer.Meta):
        fields = ActionItemBaseSerializer.Meta.fields + (
            "evidences",
            "history",
        )


class ActionPlanListSerializer(serializers.ModelSerializer):
    anomaly = AnomalySummarySerializer(read_only=True)
    owner = UserSummarySerializer(read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    pending_items_count = serializers.IntegerField(read_only=True)
    overdue_items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ActionPlan
        fields = (
            "id",
            "anomaly",
            "owner",
            "status",
            "approved_at",
            "items_count",
            "pending_items_count",
            "overdue_items_count",
            "created_at",
            "updated_at",
        )


class ActionPlanDetailSerializer(serializers.ModelSerializer):
    approved_at = serializers.DateTimeField(read_only=True, allow_null=True)
    anomaly = AnomalySummarySerializer(read_only=True)
    owner = UserSummarySerializer(read_only=True)
    items = ActionItemDetailSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    pending_items_count = serializers.IntegerField(read_only=True)
    overdue_items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ActionPlan
        fields = (
            "id",
            "anomaly",
            "owner",
            "status",
            "approved_at",
            "items_count",
            "pending_items_count",
            "overdue_items_count",
            "items",
            "created_at",
            "updated_at",
            "row_version",
        )


class ActionPlanWriteSerializer(serializers.ModelSerializer):
    anomaly = serializers.PrimaryKeyRelatedField(queryset=Anomaly.objects.all())
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ActionPlan
        fields = ("anomaly", "owner")


class ActionPlanUpdateSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ActionPlan
        fields = ("owner",)


class ActionPlanTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=ActionPlanStatus.choices)
    comment = serializers.CharField()


class ActionItemWriteSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(required=False, allow_null=True, input_formats=["%Y-%m-%d"], style=DATE_INPUT_STYLE)
    action_type = serializers.PrimaryKeyRelatedField(queryset=ActionType.objects.all())
    priority = serializers.PrimaryKeyRelatedField(queryset=Priority.objects.all(), required=False, allow_null=True)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ActionItem
        fields = (
            "code",
            "action_type",
            "priority",
            "assigned_to",
            "title",
            "description",
            "due_date",
            "is_mandatory",
            "sequence",
            "expected_evidence",
            "closure_comment",
        )
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
            "due_date": {"required": False, "allow_null": True},
            "is_mandatory": {"required": False},
            "sequence": {"required": False},
            "expected_evidence": {"required": False, "allow_blank": True},
            "closure_comment": {"required": False, "allow_blank": True},
        }


class ActionItemUpdateSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(required=False, allow_null=True, input_formats=["%Y-%m-%d"], style=DATE_INPUT_STYLE)
    action_type = serializers.PrimaryKeyRelatedField(queryset=ActionType.objects.all(), required=False)
    priority = serializers.PrimaryKeyRelatedField(queryset=Priority.objects.all(), required=False, allow_null=True)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ActionItem
        fields = (
            "code",
            "action_type",
            "priority",
            "assigned_to",
            "title",
            "description",
            "due_date",
            "is_mandatory",
            "sequence",
            "expected_evidence",
            "closure_comment",
        )
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True},
            "title": {"required": False},
            "description": {"required": False, "allow_blank": True},
            "due_date": {"required": False, "allow_null": True},
            "is_mandatory": {"required": False},
            "sequence": {"required": False},
            "expected_evidence": {"required": False, "allow_blank": True},
            "closure_comment": {"required": False, "allow_blank": True},
        }


class ActionItemTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=ActionItemStatus.choices)
    comment = serializers.CharField()
    closure_comment = serializers.CharField(required=False, allow_blank=True)


class ActionEvidenceWriteSerializer(serializers.Serializer):
    evidence_type = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)


class ActionsApiRootSerializer(serializers.Serializer):
    plans = serializers.CharField()
    items = serializers.CharField()
    my_actions = serializers.CharField()
    pending = serializers.CharField()

