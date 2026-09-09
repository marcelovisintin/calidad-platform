from rest_framework import serializers

from apps.actions.api.work_item_serializers import WorkItemUserSerializer


class ValidationItemSerializer(serializers.Serializer):
    is_overdue = serializers.BooleanField(read_only=True)
    id = serializers.UUIDField(read_only=True)
    source = serializers.ChoiceField(choices=("treatment", "observation"), read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=("pending", "blocked", "completed"), read_only=True)
    due_date = serializers.DateField(read_only=True, allow_null=True)
    responsible = WorkItemUserSerializer(read_only=True, allow_null=True)
    result = serializers.CharField(read_only=True, allow_blank=True)
    validated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    validation_comment = serializers.CharField(read_only=True, allow_blank=True)
    available = serializers.BooleanField(read_only=True)
    blockers = serializers.ListField(child=serializers.CharField(), read_only=True)
    can_validate = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
