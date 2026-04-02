from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentMethod,
    TreatmentParticipant,
    TreatmentParticipantRole,
    TreatmentRootCause,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskStatus,
)
from apps.anomalies.models import Anomaly


class UserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class AnomalySectorSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class TreatmentAnomalySummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    current_status = serializers.CharField(read_only=True)
    current_stage = serializers.CharField(read_only=True)
    reporter = UserSummarySerializer(read_only=True)
    area = AnomalySectorSerializer(read_only=True)
    anomaly_origin = AnomalySectorSerializer(read_only=True)


class TreatmentTaskAnomalySerializer(serializers.ModelSerializer):
    anomaly = TreatmentAnomalySummarySerializer(read_only=True)

    class Meta:
        model = TreatmentTaskAnomaly
        fields = ("id", "anomaly")


class TreatmentTaskSerializer(serializers.ModelSerializer):
    responsible = UserSummarySerializer(read_only=True)
    anomaly_links = TreatmentTaskAnomalySerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = TreatmentTask
        fields = (
            "id",
            "code",
            "title",
            "description",
            "status",
            "execution_date",
            "responsible",
            "root_cause",
            "is_overdue",
            "anomaly_links",
            "created_at",
            "updated_at",
        )


class TreatmentRootCauseSerializer(serializers.ModelSerializer):
    tasks = TreatmentTaskSerializer(many=True, read_only=True)

    class Meta:
        model = TreatmentRootCause
        fields = ("id", "sequence", "description", "tasks", "created_at", "updated_at")


class TreatmentParticipantSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = TreatmentParticipant
        fields = ("id", "user", "role", "note", "created_at", "updated_at")


class TreatmentAnomalyLinkSerializer(serializers.ModelSerializer):
    anomaly = TreatmentAnomalySummarySerializer(read_only=True)

    class Meta:
        model = TreatmentAnomaly
        fields = ("id", "anomaly", "is_primary", "created_at")


class TreatmentListSerializer(serializers.ModelSerializer):
    primary_anomaly = TreatmentAnomalySummarySerializer(read_only=True)

    class Meta:
        model = Treatment
        fields = (
            "id",
            "code",
            "status",
            "scheduled_for",
            "method_used",
            "observations",
            "primary_anomaly",
            "created_at",
            "updated_at",
        )


class TreatmentDetailSerializer(serializers.ModelSerializer):
    primary_anomaly = TreatmentAnomalySummarySerializer(read_only=True)
    participants = TreatmentParticipantSerializer(many=True, read_only=True)
    anomaly_links = TreatmentAnomalyLinkSerializer(many=True, read_only=True)
    root_causes = TreatmentRootCauseSerializer(many=True, read_only=True)
    tasks = TreatmentTaskSerializer(many=True, read_only=True)

    class Meta:
        model = Treatment
        fields = (
            "id",
            "code",
            "status",
            "scheduled_for",
            "method_used",
            "observations",
            "primary_anomaly",
            "participants",
            "anomaly_links",
            "root_causes",
            "tasks",
            "created_at",
            "updated_at",
            "row_version",
        )


class TreatmentCreateSerializer(serializers.Serializer):
    primary_anomaly = serializers.PrimaryKeyRelatedField(queryset=Anomaly.objects.all())
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TreatmentStatus.choices, required=False)
    method_used = serializers.ChoiceField(choices=TreatmentMethod.choices, required=False, allow_blank=True)
    observations = serializers.CharField(required=False, allow_blank=True)


class TreatmentUpdateSerializer(serializers.Serializer):
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TreatmentStatus.choices, required=False)
    method_used = serializers.ChoiceField(choices=TreatmentMethod.choices, required=False, allow_blank=True)
    observations = serializers.CharField(required=False, allow_blank=True)


class TreatmentAddAnomalySerializer(serializers.Serializer):
    anomaly = serializers.PrimaryKeyRelatedField(queryset=Anomaly.objects.all())


class TreatmentAddParticipantSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    role = serializers.ChoiceField(choices=TreatmentParticipantRole.choices, required=False, default=TreatmentParticipantRole.CONVOKED)
    note = serializers.CharField(required=False, allow_blank=True)


class TreatmentAddRootCauseSerializer(serializers.Serializer):
    description = serializers.CharField()


class TreatmentAddTaskSerializer(serializers.Serializer):
    root_cause = serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all(), required=False, allow_null=True)
    title = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)
    execution_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TreatmentTaskStatus.choices, required=False)
    anomaly_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class TreatmentUpdateTaskSerializer(serializers.Serializer):
    root_cause = serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all(), required=False, allow_null=True)
    title = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)
    execution_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TreatmentTaskStatus.choices, required=False)
    anomaly_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class TreatmentCandidateSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    current_status = serializers.CharField(read_only=True)
    current_stage = serializers.CharField(read_only=True)
    reporter = UserSummarySerializer(read_only=True)
    area = AnomalySectorSerializer(read_only=True)
    anomaly_origin = AnomalySectorSerializer(read_only=True)
    detected_at = serializers.DateTimeField(read_only=True)


class TreatmentsApiRootSerializer(serializers.Serializer):
    treatments = serializers.CharField()
    candidates = serializers.CharField()
