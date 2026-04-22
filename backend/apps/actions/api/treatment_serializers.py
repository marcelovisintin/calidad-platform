from pathlib import Path

from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentEvidence,
    TreatmentMethod,
    TreatmentParticipant,
    TreatmentParticipantRole,
    TreatmentRootCause,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskEvidence,
    TreatmentTaskStatus,
)
from apps.anomalies.models import Anomaly, AnomalyAttachment

ALLOWED_EVIDENCE_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/zip",
    "application/x-zip-compressed",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
}

ALLOWED_EVIDENCE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
    ".csv",
    ".rtf",
    ".odt",
    ".ods",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

def _validate_objective_file(file_obj):
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    file_name = (getattr(file_obj, "name", "") or "").lower()
    extension = Path(file_name).suffix

    if content_type in ALLOWED_EVIDENCE_CONTENT_TYPES:
        return file_obj
    if extension in ALLOWED_EVIDENCE_EXTENSIONS:
        return file_obj
    raise serializers.ValidationError("Solo se permiten evidencias en formato imagen, PDF, Word, Excel, texto o ZIP.")


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


class AnomalyAttachmentSummarySerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = AnomalyAttachment
        fields = ("id", "original_name", "content_type", "file_url", "uploaded_by", "created_at")

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = reverse("api:anomalies:attachment-download", kwargs={"attachment_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


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
    attachments = AnomalyAttachmentSummarySerializer(many=True, read_only=True)


class TreatmentEvidenceSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentEvidence
        fields = (
            "id",
            "original_name",
            "content_type",
            "note",
            "file_url",
            "uploaded_by",
            "created_at",
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = reverse("api:actions:treatment-evidence-download", kwargs={"evidence_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


class TreatmentTaskEvidenceSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentTaskEvidence
        fields = (
            "id",
            "original_name",
            "content_type",
            "note",
            "file_url",
            "uploaded_by",
            "created_at",
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = reverse("api:actions:treatment-task-evidence-download", kwargs={"evidence_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


class TreatmentTaskAnomalySerializer(serializers.ModelSerializer):
    anomaly = TreatmentAnomalySummarySerializer(read_only=True)

    class Meta:
        model = TreatmentTaskAnomaly
        fields = ("id", "anomaly")


class TreatmentTaskSerializer(serializers.ModelSerializer):
    responsible = UserSummarySerializer(read_only=True)
    anomaly_links = TreatmentTaskAnomalySerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    evidences = TreatmentTaskEvidenceSerializer(many=True, read_only=True)

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
            "evidences",
            "created_at",
            "updated_at",
        )



class TreatmentTaskHistoryRootCauseSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    sequence = serializers.IntegerField(read_only=True)
    description = serializers.CharField(read_only=True)


class TreatmentTaskHistoryTreatmentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    primary_anomaly = TreatmentAnomalySummarySerializer(read_only=True)


class TreatmentTaskHistorySerializer(serializers.ModelSerializer):
    responsible = UserSummarySerializer(read_only=True)
    treatment = TreatmentTaskHistoryTreatmentSerializer(read_only=True)
    anomalies = serializers.SerializerMethodField()
    root_cause = TreatmentTaskHistoryRootCauseSerializer(read_only=True)
    evidences = TreatmentTaskEvidenceSerializer(many=True, read_only=True)
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
            "is_overdue",
            "responsible",
            "treatment",
            "anomalies",
            "root_cause",
            "evidences",
            "created_at",
            "updated_at",
        )

    def get_anomalies(self, obj):
        anomalies = [link.anomaly for link in obj.anomaly_links.all() if getattr(link, "anomaly", None)]
        if not anomalies and getattr(obj.treatment, "primary_anomaly", None):
            anomalies = [obj.treatment.primary_anomaly]
        return TreatmentAnomalySummarySerializer(anomalies, many=True, context=self.context).data
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
    evidences = TreatmentEvidenceSerializer(many=True, read_only=True)

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
            "evidences",
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
    root_cause = serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all())
    title = serializers.CharField(allow_blank=False)
    description = serializers.CharField(allow_blank=False)
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    execution_date = serializers.DateField()
    status = serializers.ChoiceField(choices=TreatmentTaskStatus.choices, required=False, default=TreatmentTaskStatus.PENDING)
    anomaly_ids = serializers.ListField(child=serializers.UUIDField(), required=True, allow_empty=False)


class TreatmentUpdateTaskSerializer(serializers.Serializer):
    root_cause = serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all(), required=False, allow_null=True)
    title = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)
    execution_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TreatmentTaskStatus.choices, required=False)
    anomaly_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class TreatmentEvidenceWriteSerializer(serializers.Serializer):
    file = serializers.FileField()
    note = serializers.CharField(required=False, allow_blank=True)
    original_name = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        return _validate_objective_file(value)


class TreatmentTaskEvidenceWriteSerializer(serializers.Serializer):
    file = serializers.FileField()
    note = serializers.CharField(required=False, allow_blank=True)
    original_name = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        return _validate_objective_file(value)


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

