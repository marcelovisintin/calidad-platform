from rest_framework import serializers
from apps.anomalies.api.serializers import AnomalyAttachmentSerializer

from apps.actions.api.treatment_serializers import (
    TreatmentTaskEvidenceSerializer,
    TreatmentTaskHistoryRootCauseSerializer,
)


class WorkItemUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class WorkItemAnomalySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    current_status = serializers.CharField(read_only=True)
    current_stage = serializers.CharField(read_only=True)


class WorkItemTreatmentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class WorkItemStatusEvidenceSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    from_status = serializers.CharField(read_only=True)
    to_status = serializers.CharField(read_only=True)
    note = serializers.CharField(read_only=True)
    changed_by = WorkItemUserSerializer(read_only=True, allow_null=True)
    changed_at = serializers.DateTimeField(read_only=True)


class ActionWorkItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    source = serializers.ChoiceField(choices=("treatment", "observation"), read_only=True)
    derived_from_lesson = serializers.BooleanField(read_only=True, default=False)
    code = serializers.CharField(read_only=True, allow_blank=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    status = serializers.CharField(read_only=True)
    due_date = serializers.DateField(read_only=True, allow_null=True)
    completed_on = serializers.DateField(read_only=True, allow_null=True)
    effectiveness_due_date = serializers.DateField(read_only=True, allow_null=True)
    is_overdue = serializers.BooleanField(read_only=True)
    responsible = WorkItemUserSerializer(read_only=True, allow_null=True)
    completed_by = WorkItemUserSerializer(read_only=True, allow_null=True)
    treatment = WorkItemTreatmentSerializer(read_only=True, allow_null=True)
    anomalies = WorkItemAnomalySerializer(many=True, read_only=True)
    root_causes = TreatmentTaskHistoryRootCauseSerializer(many=True, read_only=True)
    evidences = serializers.SerializerMethodField()
    status_evidences = WorkItemStatusEvidenceSerializer(many=True, read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)
    can_manage = serializers.BooleanField(read_only=True)
    can_update_status = serializers.BooleanField(read_only=True)
    can_add_evidence = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_evidences(self, obj):
        serializer = AnomalyAttachmentSerializer if obj["source"] == "observation" else TreatmentTaskEvidenceSerializer
        return serializer(obj["evidences"], many=True, context=self.context).data
