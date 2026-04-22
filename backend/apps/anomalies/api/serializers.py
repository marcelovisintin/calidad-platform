from pathlib import Path

from django.db.models import Q
from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.actions.models import ActionItem, ActionItemStatus, ActionPlan, TreatmentTask
from apps.anomalies.models import (
    AnalysisMethod,
    Anomaly,
    AnomalyAttachment,
    AnomalyCauseAnalysis,
    AnomalyClassification,
    AnomalyCodeReservation,
    AnomalyComment,
    AnomalyCommentType,
    AnomalyEffectivenessCheck,
    AnomalyInitialVerification,
    AnomalyImmediateAction,
    AnomalyLearning,
    AnomalyParticipant,
    AnomalyProposal,
    AnomalyStage,
    AnomalyStatus,
    AnomalyStatusHistory,
    ParticipantRole,
)
from apps.catalog.models import Area, Line, Site
from apps.anomalies.services.classification_rules import can_modify_classification, can_unlock_classification_change

DATETIME_INPUT_STYLE = {
    "input_type": "text",
    "placeholder": "YYYY-MM-DDTHH:MM:SS-03:00",
}

OPEN_ACTION_ITEM_STATUSES = {ActionItemStatus.PENDING, ActionItemStatus.IN_PROGRESS}

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


class CurrentResponsibleMixin:
    def _prefetched_related_list(self, instance, relation_name: str):
        cache = getattr(instance, "_prefetched_objects_cache", {})
        if relation_name in cache:
            return list(cache[relation_name])
        relation = getattr(instance, relation_name, None)
        if relation is None:
            return []
        try:
            return list(relation.all())
        except AttributeError:
            return []

    def _resolve_current_responsible(self, obj):
        if getattr(obj, "owner_id", None):
            return obj.owner

        action_plans = self._prefetched_related_list(obj, "action_plans")
        active_plans = [plan for plan in action_plans if plan.status == "active"]

        for plan in active_plans:
            if getattr(plan, "owner_id", None):
                return plan.owner

        candidate_plans = active_plans or action_plans
        for plan in candidate_plans:
            items = self._prefetched_related_list(plan, "items")
            for item in items:
                if item.status in OPEN_ACTION_ITEM_STATUSES and getattr(item, "assigned_to_id", None):
                    return item.assigned_to
        return None

    def get_current_responsible(self, obj):
        responsible = self._resolve_current_responsible(obj)
        return UserSummarySerializer(responsible).data if responsible else None


class ClassificationControlsMixin:
    def get_can_modify_classification(self, obj):
        return can_modify_classification(obj)

    def get_can_unlock_classification(self, obj):
        return can_unlock_classification_change(obj)


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
    class Meta:
        model = Line
        fields = ("id", "code", "name")


class CatalogSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class ActionItemSummarySerializer(serializers.ModelSerializer):
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
        )


class ActionPlanSummarySerializer(serializers.ModelSerializer):
    approved_at = serializers.DateTimeField(read_only=True, allow_null=True)
    owner = UserSummarySerializer(read_only=True)
    items = ActionItemSummarySerializer(many=True, read_only=True)

    class Meta:
        model = ActionPlan
        fields = ("id", "status", "approved_at", "owner", "items")


class TreatmentTaskPlanSerializer(serializers.ModelSerializer):
    responsible = UserSummarySerializer(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    treatment = serializers.SerializerMethodField()
    root_cause_description = serializers.SerializerMethodField()

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
            "root_cause_description",
        )

    def get_treatment(self, obj):
        treatment = getattr(obj, "treatment", None)
        if not treatment:
            return None
        return {
            "id": treatment.id,
            "code": treatment.code,
            "status": treatment.status,
        }

    def get_root_cause_description(self, obj):
        root_cause = getattr(obj, "root_cause", None)
        return getattr(root_cause, "description", "") if root_cause else ""

class AnomalyStatusHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyStatusHistory
        fields = (
            "id",
            "from_status",
            "to_status",
            "from_stage",
            "to_stage",
            "comment",
            "changed_at",
            "changed_by",
        )


class AnomalyCommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyComment
        fields = ("id", "body", "comment_type", "author", "created_at")



class AnomalyCodeReservationSerializer(serializers.ModelSerializer):
    reserved_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyCodeReservation
        fields = ("id", "code", "year", "sequence", "reserved_by", "created_at")

class AnomalyAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = AnomalyAttachment
        fields = (
            "id",
            "original_name",
            "content_type",
            "file_url",
            "uploaded_by",
            "created_at",
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = reverse("api:anomalies:attachment-download", kwargs={"attachment_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


class AnomalyParticipantSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyParticipant
        fields = ("id", "user", "role", "note", "created_at", "updated_at")


class AnomalyInitialVerificationSerializer(serializers.ModelSerializer):
    verified_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyInitialVerification
        fields = (
            "id",
            "verified_by",
            "verified_at",
            "material_checked",
            "machine_checked",
            "method_checked",
            "manpower_checked",
            "milieu_checked",
            "measurement_checked",
            "material_notes",
            "machine_notes",
            "method_notes",
            "manpower_notes",
            "milieu_notes",
            "measurement_notes",
            "summary",
        )


class AnomalyClassificationSerializer(serializers.ModelSerializer):
    classified_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyClassification
        fields = (
            "id",
            "classified_by",
            "classified_at",
            "containment_required",
            "requires_action_plan",
            "requires_effectiveness_verification",
            "impact_scope",
            "summary",
        )


class AnomalyCauseAnalysisSerializer(serializers.ModelSerializer):
    analyzed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyCauseAnalysis
        fields = (
            "id",
            "analyzed_by",
            "analyzed_at",
            "method_used",
            "immediate_cause",
            "root_cause",
            "summary",
        )


class AnomalyProposalSerializer(serializers.ModelSerializer):
    proposed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyProposal
        fields = (
            "id",
            "title",
            "description",
            "proposed_by",
            "proposed_at",
            "is_selected",
            "sequence",
        )


class AnomalyEffectivenessCheckSerializer(serializers.ModelSerializer):
    verified_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyEffectivenessCheck
        fields = (
            "id",
            "verified_by",
            "verified_at",
            "is_effective",
            "evidence_summary",
            "comment",
            "recommended_stage",
        )


class AnomalyLearningSerializer(serializers.ModelSerializer):
    recorded_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyLearning
        fields = (
            "id",
            "recorded_by",
            "recorded_at",
            "standardization_actions",
            "lessons_learned",
            "document_changes",
            "shared_with",
            "shared_at",
        )



class AnomalyImmediateActionSerializer(serializers.ModelSerializer):
    responsible = UserSummarySerializer(read_only=True)

    class Meta:
        model = AnomalyImmediateAction
        fields = (
            "id",
            "responsible",
            "action_date",
            "effectiveness_verified_at",
            "observation",
            "actions_taken",
            "effectiveness_comment",
            "closure_comment",
        )

class AnomalyListSerializer(CurrentResponsibleMixin, ClassificationControlsMixin, serializers.ModelSerializer):
    site = SiteSummarySerializer(read_only=True)
    area = AreaSummarySerializer(read_only=True)
    line = LineSummarySerializer(read_only=True)
    reporter = UserSummarySerializer(read_only=True)
    owner = UserSummarySerializer(read_only=True)
    current_responsible = serializers.SerializerMethodField()
    anomaly_type = CatalogSummarySerializer(read_only=True)
    anomaly_origin = CatalogSummarySerializer(read_only=True)
    severity = CatalogSummarySerializer(read_only=True)
    priority = CatalogSummarySerializer(read_only=True)
    can_modify_classification = serializers.SerializerMethodField()
    can_unlock_classification = serializers.SerializerMethodField()

    class Meta:
        model = Anomaly
        fields = (
            "id",
            "code",
            "title",
            "current_status",
            "current_stage",
            "detected_at",
            "site",
            "area",
            "line",
            "reporter",
            "owner",
            "current_responsible",
            "anomaly_type",
            "anomaly_origin",
            "severity",
            "priority",
            "can_modify_classification",
            "can_unlock_classification",
            "classification_change_count",
            "classification_change_unlocked",
            "manufacturing_order_number",
            "affected_quantity",
            "affected_process",
            "due_at",
            "closed_at",
            "reopened_count",
        )


class AnomalyDetailSerializer(CurrentResponsibleMixin, ClassificationControlsMixin, serializers.ModelSerializer):
    site = SiteSummarySerializer(read_only=True)
    area = AreaSummarySerializer(read_only=True)
    line = LineSummarySerializer(read_only=True)
    reporter = UserSummarySerializer(read_only=True)
    owner = UserSummarySerializer(read_only=True)
    current_responsible = serializers.SerializerMethodField()
    duplicate_of = AnomalyListSerializer(read_only=True)
    anomaly_type = CatalogSummarySerializer(read_only=True)
    anomaly_origin = CatalogSummarySerializer(read_only=True)
    severity = CatalogSummarySerializer(read_only=True)
    priority = CatalogSummarySerializer(read_only=True)
    can_modify_classification = serializers.SerializerMethodField()
    can_unlock_classification = serializers.SerializerMethodField()
    comments = AnomalyCommentSerializer(many=True, read_only=True)
    attachments = AnomalyAttachmentSerializer(many=True, read_only=True)
    participants = AnomalyParticipantSerializer(many=True, read_only=True)
    proposals = AnomalyProposalSerializer(many=True, read_only=True)
    effectiveness_checks = AnomalyEffectivenessCheckSerializer(many=True, read_only=True)
    status_history = AnomalyStatusHistorySerializer(many=True, read_only=True)
    initial_verification = AnomalyInitialVerificationSerializer(read_only=True)
    classification = AnomalyClassificationSerializer(read_only=True)
    cause_analysis = AnomalyCauseAnalysisSerializer(read_only=True)
    learning = AnomalyLearningSerializer(read_only=True)
    immediate_action = AnomalyImmediateActionSerializer(read_only=True)
    action_plans = ActionPlanSummarySerializer(many=True, read_only=True)
    treatment_tasks = serializers.SerializerMethodField()

    def get_treatment_tasks(self, obj):
        queryset = (
            TreatmentTask.objects.filter(
                Q(treatment__primary_anomaly=obj)
                | Q(treatment__anomaly_links__anomaly=obj)
                | Q(anomaly_links__anomaly=obj)
            )
            .select_related("responsible", "root_cause", "treatment")
            .distinct()
            .order_by("execution_date", "created_at")
        )
        return TreatmentTaskPlanSerializer(queryset, many=True, context=self.context).data

    class Meta:
        model = Anomaly
        fields = (
            "id",
            "code",
            "title",
            "description",
            "current_status",
            "current_stage",
            "detected_at",
            "site",
            "area",
            "line",
            "reporter",
            "owner",
            "current_responsible",
            "duplicate_of",
            "anomaly_type",
            "anomaly_origin",
            "severity",
            "priority",
            "can_modify_classification",
            "can_unlock_classification",
            "classification_change_count",
            "classification_change_unlocked",
            "manufacturing_order_number",
            "affected_quantity",
            "affected_process",
            "due_at",
            "closed_at",
            "last_transition_at",
            "containment_summary",
            "classification_summary",
            "root_cause_summary",
            "resolution_summary",
            "result_summary",
            "effectiveness_summary",
            "closure_comment",
            "cancellation_reason",
            "reopened_count",
            "comments",
            "attachments",
            "participants",
            "proposals",
            "effectiveness_checks",
            "status_history",
            "initial_verification",
            "classification",
            "cause_analysis",
            "learning",
            "immediate_action",
            "action_plans",
            "treatment_tasks",
            "created_at",
            "updated_at",
            "row_version",
        )


class AnomalyCreateSerializer(serializers.ModelSerializer):
    detected_at = serializers.DateTimeField(style=DATETIME_INPUT_STYLE)
    due_at = serializers.DateTimeField(required=False, allow_null=True, style=DATETIME_INPUT_STYLE)
    registration_comment = serializers.CharField(write_only=True, required=False, allow_blank=True)
    code_reservation_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Anomaly
        fields = (
            "code",
            "title",
            "description",
            "site",
            "area",
            "line",
            "owner",
            "anomaly_type",
            "anomaly_origin",
            "severity",
            "priority",
            "duplicate_of",
            "detected_at",
            "manufacturing_order_number",
            "affected_quantity",
            "affected_process",
            "due_at",
            "containment_summary",
            "resolution_summary",
            "result_summary",
            "registration_comment",
            "code_reservation_id",
        )
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True},
            "line": {"required": False, "allow_null": True},
            "owner": {"required": False, "allow_null": True},
            "duplicate_of": {"required": False, "allow_null": True},
            "containment_summary": {"required": False, "allow_blank": True},
            "resolution_summary": {"required": False, "allow_blank": True},
            "result_summary": {"required": False, "allow_blank": True},
            "manufacturing_order_number": {"required": False, "allow_blank": True},
            "affected_quantity": {"required": False, "allow_null": True},
            "affected_process": {"required": False, "allow_blank": True},
            "severity": {"required": False, "allow_null": True},
            "code_reservation_id": {"required": False, "allow_null": True},
        }


class AnomalyUpdateSerializer(serializers.ModelSerializer):
    detected_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)
    due_at = serializers.DateTimeField(required=False, allow_null=True, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = Anomaly
        fields = (
            "title",
            "description",
            "site",
            "area",
            "line",
            "owner",
            "anomaly_type",
            "anomaly_origin",
            "severity",
            "priority",
            "duplicate_of",
            "detected_at",
            "manufacturing_order_number",
            "affected_quantity",
            "affected_process",
            "due_at",
            "containment_summary",
            "resolution_summary",
            "result_summary",
        )
        extra_kwargs = {
            "title": {"required": False},
            "description": {"required": False},
            "site": {"required": False},
            "area": {"required": False},
            "line": {"required": False, "allow_null": True},
            "owner": {"required": False, "allow_null": True},
            "anomaly_type": {"required": False},
            "anomaly_origin": {"required": False},
            "severity": {"required": False, "allow_null": True},
            "priority": {"required": False},
            "duplicate_of": {"required": False, "allow_null": True},
            "manufacturing_order_number": {"required": False, "allow_blank": True},
            "affected_quantity": {"required": False, "allow_null": True},
            "affected_process": {"required": False, "allow_blank": True},
            "containment_summary": {"required": False, "allow_blank": True},
            "resolution_summary": {"required": False, "allow_blank": True},
            "result_summary": {"required": False, "allow_blank": True},
        }


class AnomalyTransitionSerializer(serializers.Serializer):
    target_stage = serializers.ChoiceField(choices=AnomalyStage.choices, required=False)
    target_status = serializers.ChoiceField(choices=AnomalyStatus.choices, required=False)
    comment = serializers.CharField()

    def validate(self, attrs):
        if not attrs.get("target_stage") and not attrs.get("target_status"):
            raise serializers.ValidationError("Debe informar target_stage o target_status.")
        return attrs


class AnomalyCommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    comment_type = serializers.ChoiceField(choices=AnomalyCommentType.choices, required=False)


class AnomalyParticipantWriteSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    role = serializers.ChoiceField(choices=ParticipantRole.choices)
    note = serializers.CharField(required=False, allow_blank=True)


class AnomalyInitialVerificationWriteSerializer(serializers.ModelSerializer):
    verified_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = AnomalyInitialVerification
        fields = (
            "verified_at",
            "material_checked",
            "machine_checked",
            "method_checked",
            "manpower_checked",
            "milieu_checked",
            "measurement_checked",
            "material_notes",
            "machine_notes",
            "method_notes",
            "manpower_notes",
            "milieu_notes",
            "measurement_notes",
            "summary",
        )


class AnomalyClassificationWriteSerializer(serializers.ModelSerializer):
    classified_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = AnomalyClassification
        fields = (
            "classified_at",
            "containment_required",
            "requires_action_plan",
            "requires_effectiveness_verification",
            "impact_scope",
            "summary",
        )


class AnomalyCauseAnalysisWriteSerializer(serializers.ModelSerializer):
    analyzed_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = AnomalyCauseAnalysis
        fields = (
            "analyzed_at",
            "method_used",
            "immediate_cause",
            "root_cause",
            "summary",
        )


class AnomalyProposalWriteSerializer(serializers.ModelSerializer):
    proposed_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = AnomalyProposal
        fields = ("title", "description", "proposed_at", "is_selected", "sequence")
        extra_kwargs = {
            "is_selected": {"required": False},
            "sequence": {"required": False},
        }


class AnomalyEffectivenessCheckWriteSerializer(serializers.ModelSerializer):
    verified_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = AnomalyEffectivenessCheck
        fields = ("verified_at", "is_effective", "evidence_summary", "comment", "recommended_stage")
        extra_kwargs = {
            "evidence_summary": {"required": False, "allow_blank": True},
            "recommended_stage": {"required": False, "allow_blank": True},
        }


class AnomalyLearningWriteSerializer(serializers.ModelSerializer):
    recorded_at = serializers.DateTimeField(required=False, style=DATETIME_INPUT_STYLE)
    shared_at = serializers.DateTimeField(required=False, allow_null=True, style=DATETIME_INPUT_STYLE)

    class Meta:
        model = AnomalyLearning
        fields = (
            "recorded_at",
            "standardization_actions",
            "lessons_learned",
            "document_changes",
            "shared_with",
            "shared_at",
        )



class AnomalyImmediateActionWriteSerializer(serializers.Serializer):
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    action_date = serializers.DateField()
    effectiveness_verified_at = serializers.DateTimeField(style=DATETIME_INPUT_STYLE)
    observation = serializers.CharField()
    actions_taken = serializers.CharField()
    effectiveness_comment = serializers.CharField(required=False, allow_blank=True)
    closure_comment = serializers.CharField(required=False, allow_blank=True)

class AnomalyAttachmentWriteSerializer(serializers.Serializer):
    file = serializers.FileField()
    original_name = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        return _validate_objective_file(value)


class WorkflowMetadataSerializer(serializers.Serializer):
    statuses = serializers.DictField(child=serializers.CharField())
    stages = serializers.DictField(child=serializers.CharField())
    analysis_methods = serializers.DictField(child=serializers.CharField())
    participant_roles = serializers.DictField(child=serializers.CharField())
    comment_types = serializers.DictField(child=serializers.CharField())

















