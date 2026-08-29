from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentEffectivenessValidationResult,
    TreatmentEvidence,
    TreatmentLearnedLesson,
    TreatmentLearnedLessonEvidence,
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
from apps.audit.models import AuditEvent
from apps.anomalies.models import Anomaly, AnomalyAttachment
from common.upload_validation import validate_evidence_file

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


class TreatmentParticipantOptionSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    sector = AnomalySectorSerializer(source="primary_sector", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "full_name", "access_level", "sector")


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
    affected_process = serializers.CharField(read_only=True)
    reporter = UserSummarySerializer(read_only=True)
    area = AnomalySectorSerializer(read_only=True)
    imputed_area = AnomalySectorSerializer(read_only=True)
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


class TreatmentLearnedLessonEvidenceSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentLearnedLessonEvidence
        fields = ("id", "original_name", "content_type", "file_url", "uploaded_by", "created_at")

    def get_file_url(self, obj):
        request = self.context.get("request")
        url = reverse("api:actions:treatment-learned-lesson-evidence-download", kwargs={"evidence_id": obj.pk})
        return request.build_absolute_uri(url) if request else url


class TreatmentLearnedLessonSerializer(serializers.ModelSerializer):
    saved_by = UserSummarySerializer(read_only=True)
    evidences = TreatmentLearnedLessonEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = TreatmentLearnedLesson
        fields = (
            "id",
            "has_learning",
            "learned_text",
            "no_learning_reason",
            "procedure_modified",
            "procedure_modification_notes",
            "saved_by",
            "saved_at",
            "evidences",
            "created_at",
            "updated_at",
        )


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


class TreatmentTaskHistoryRootCauseSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    sequence = serializers.IntegerField(read_only=True)
    description = serializers.CharField(read_only=True)


class TreatmentTaskSerializer(serializers.ModelSerializer):
    responsible = UserSummarySerializer(read_only=True)
    anomaly_links = TreatmentTaskAnomalySerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    evidences = TreatmentTaskEvidenceSerializer(many=True, read_only=True)
    root_causes = TreatmentTaskHistoryRootCauseSerializer(many=True, read_only=True)
    can_manage = serializers.SerializerMethodField()
    can_update_status = serializers.SerializerMethodField()
    can_add_evidence = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentTask
        fields = (
            "id",
            "code",
            "title",
            "description",
            "status",
            "execution_date",
            "completed_at",
            "responsible",
            "root_cause",
            "root_causes",
            "is_overdue",
            "anomaly_links",
            "evidences",
            "can_manage",
            "can_update_status",
            "can_add_evidence",
            "created_at",
            "updated_at",
        )

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_can_manage(self, obj):
        from apps.actions.services.treatment_service import can_manage_treatment

        return can_manage_treatment(self._user(), obj.treatment)

    def get_can_update_status(self, obj):
        from apps.accounts.services.access_policy import can_execute_assignment

        return can_execute_assignment(self._user(), obj.responsible_id)

    def get_can_add_evidence(self, obj):
        return self.get_can_update_status(obj)


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
    root_causes = TreatmentTaskHistoryRootCauseSerializer(many=True, read_only=True)
    evidences = TreatmentTaskEvidenceSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    can_manage = serializers.SerializerMethodField()
    can_update_status = serializers.SerializerMethodField()
    can_add_evidence = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentTask
        fields = (
            "id",
            "code",
            "title",
            "description",
            "status",
            "execution_date",
            "completed_at",
            "is_overdue",
            "responsible",
            "treatment",
            "anomalies",
            "root_cause",
            "root_causes",
            "evidences",
            "can_manage",
            "can_update_status",
            "can_add_evidence",
            "created_at",
            "updated_at",
        )

    def get_anomalies(self, obj):
        anomalies = [link.anomaly for link in obj.anomaly_links.all() if getattr(link, "anomaly", None)]
        if not anomalies and getattr(obj.treatment, "primary_anomaly", None):
            anomalies = [obj.treatment.primary_anomaly]
        return TreatmentAnomalySummarySerializer(anomalies, many=True, context=self.context).data

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_can_manage(self, obj):
        from apps.actions.services.treatment_service import can_manage_treatment

        return can_manage_treatment(self._user(), obj.treatment)

    def get_can_update_status(self, obj):
        from apps.accounts.services.access_policy import can_execute_assignment

        return can_execute_assignment(self._user(), obj.responsible_id)

    def get_can_add_evidence(self, obj):
        return self.get_can_update_status(obj)


class TreatmentAuditEventSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)

    class Meta:
        model = AuditEvent
        fields = ("id", "action", "actor", "created_at")


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
    responsible = UserSummarySerializer(read_only=True)
    convocation_confirmed_by = UserSummarySerializer(read_only=True)
    effectiveness_responsible = UserSummarySerializer(read_only=True)
    effectiveness_validated_by = UserSummarySerializer(read_only=True)
    validation_state = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    learned_lesson = TreatmentLearnedLessonSerializer(read_only=True)
    can_manage = serializers.SerializerMethodField()
    can_validate_effectiveness = serializers.SerializerMethodField()
    can_reconfigure = serializers.SerializerMethodField()

    class Meta:
        model = Treatment
        fields = (
            "id",
            "code",
            "status",
            "scheduled_for",
            "treatment_location",
            "convocation_confirmed_at",
            "convocation_confirmed_by",
            "method_used",
            "observations",
            "effectiveness_evaluation_date",
            "effectiveness_responsible",
            "effectiveness_validation_result",
            "effectiveness_validated_at",
            "effectiveness_validated_by",
            "effectiveness_validation_comment",
            "validation_state",
            "is_locked",
            "learned_lesson",
            "can_manage",
            "can_validate_effectiveness",
            "can_reconfigure",
            "primary_anomaly",
            "responsible",
            "created_at",
            "updated_at",
        )

    def get_validation_state(self, obj):
        from apps.actions.services.treatment_service import get_treatment_validation_state

        return get_treatment_validation_state(obj)

    def get_is_locked(self, obj):
        from apps.actions.services.treatment_service import is_treatment_closed_by_effective_validation

        return is_treatment_closed_by_effective_validation(obj)

    def get_can_manage(self, obj):
        from apps.actions.services.treatment_service import can_manage_treatment

        request = self.context.get("request")
        return can_manage_treatment(getattr(request, "user", None), obj)

    def get_can_validate_effectiveness(self, obj):
        from apps.actions.services.treatment_service import can_validate_treatment_effectiveness

        request = self.context.get("request")
        return can_validate_treatment_effectiveness(getattr(request, "user", None), obj)

    def get_can_reconfigure(self, obj):
        from apps.actions.services.treatment_service import can_reconfigure_treatment

        request = self.context.get("request")
        return can_reconfigure_treatment(getattr(request, "user", None), obj)


class TreatmentDetailSerializer(serializers.ModelSerializer):
    primary_anomaly = TreatmentAnomalySummarySerializer(read_only=True)
    responsible = UserSummarySerializer(read_only=True)
    convocation_confirmed_by = UserSummarySerializer(read_only=True)
    effectiveness_responsible = UserSummarySerializer(read_only=True)
    effectiveness_validated_by = UserSummarySerializer(read_only=True)
    validation_state = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    participants = TreatmentParticipantSerializer(many=True, read_only=True)
    anomaly_links = TreatmentAnomalyLinkSerializer(many=True, read_only=True)
    root_causes = TreatmentRootCauseSerializer(many=True, read_only=True)
    tasks = TreatmentTaskSerializer(many=True, read_only=True)
    evidences = TreatmentEvidenceSerializer(many=True, read_only=True)
    audit_events = serializers.SerializerMethodField()
    learned_lesson = TreatmentLearnedLessonSerializer(read_only=True)
    can_manage = serializers.SerializerMethodField()
    can_validate_effectiveness = serializers.SerializerMethodField()
    can_reconfigure = serializers.SerializerMethodField()

    class Meta:
        model = Treatment
        fields = (
            "id",
            "code",
            "status",
            "scheduled_for",
            "treatment_location",
            "convocation_confirmed_at",
            "convocation_confirmed_by",
            "method_used",
            "observations",
            "effectiveness_evaluation_date",
            "effectiveness_responsible",
            "effectiveness_validation_result",
            "effectiveness_validated_at",
            "effectiveness_validated_by",
            "effectiveness_validation_comment",
            "validation_state",
            "is_locked",
            "primary_anomaly",
            "responsible",
            "participants",
            "anomaly_links",
            "root_causes",
            "tasks",
            "evidences",
            "audit_events",
            "learned_lesson",
            "can_manage",
            "can_validate_effectiveness",
            "can_reconfigure",
            "created_at",
            "updated_at",
            "row_version",
        )

    def get_validation_state(self, obj):
        from apps.actions.services.treatment_service import get_treatment_validation_state

        return get_treatment_validation_state(obj)

    def get_is_locked(self, obj):
        from apps.actions.services.treatment_service import is_treatment_closed_by_effective_validation

        return is_treatment_closed_by_effective_validation(obj)

    def get_can_manage(self, obj):
        from apps.actions.services.treatment_service import can_manage_treatment

        request = self.context.get("request")
        return can_manage_treatment(getattr(request, "user", None), obj)

    def get_can_validate_effectiveness(self, obj):
        from apps.actions.services.treatment_service import can_validate_treatment_effectiveness

        request = self.context.get("request")
        return can_validate_treatment_effectiveness(getattr(request, "user", None), obj)

    def get_can_reconfigure(self, obj):
        from apps.actions.services.treatment_service import can_reconfigure_treatment

        request = self.context.get("request")
        return can_reconfigure_treatment(getattr(request, "user", None), obj)

    def get_audit_events(self, obj):
        queryset = AuditEvent.objects.select_related("actor").filter(
            entity_type="actions.treatment",
            entity_id=obj.pk,
        ).order_by("-created_at")[:50]
        return TreatmentAuditEventSerializer(queryset, many=True, context=self.context).data


class TreatmentCreateSerializer(serializers.Serializer):
    primary_anomaly = serializers.PrimaryKeyRelatedField(queryset=Anomaly.objects.all())
    force_create_new = serializers.BooleanField(required=False, default=False, write_only=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    treatment_location = serializers.CharField(required=False, allow_blank=True, max_length=200)
    status = serializers.ChoiceField(choices=TreatmentStatus.choices, required=False)
    method_used = serializers.ChoiceField(choices=TreatmentMethod.choices, required=False, allow_blank=True)
    observations = serializers.CharField(required=False, allow_blank=True)


class TreatmentUpdateSerializer(serializers.Serializer):
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    treatment_location = serializers.CharField(required=False, allow_blank=True, max_length=200)
    status = serializers.ChoiceField(choices=TreatmentStatus.choices, required=False)
    method_used = serializers.ChoiceField(choices=TreatmentMethod.choices, required=False, allow_blank=True)
    observations = serializers.CharField(required=False, allow_blank=True)
    effectiveness_evaluation_date = serializers.DateField(required=False, allow_null=True)
    effectiveness_responsible = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )


class TreatmentConfirmConvocationSerializer(serializers.Serializer):
    scheduled_for = serializers.DateTimeField(required=True, allow_null=False)
    treatment_location = serializers.CharField(required=False, allow_blank=True, max_length=200)


class TreatmentAddAnomalySerializer(serializers.Serializer):
    anomaly = serializers.PrimaryKeyRelatedField(queryset=Anomaly.objects.all())


class TreatmentReconfigureSerializer(serializers.Serializer):
    related_anomalies = serializers.PrimaryKeyRelatedField(
        queryset=Anomaly.objects.all(),
        many=True,
        required=False,
    )
    responsible = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
    )
    reason = serializers.CharField(allow_blank=False)


class TreatmentAddParticipantSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    role = serializers.ChoiceField(
        choices=[(TreatmentParticipantRole.CONVOKED, "Convocado")],
        required=False,
        default=TreatmentParticipantRole.CONVOKED,
    )
    note = serializers.CharField(required=False, allow_blank=True)


class TreatmentAddRootCauseSerializer(serializers.Serializer):
    description = serializers.CharField()


class TreatmentAddTaskSerializer(serializers.Serializer):
    root_cause = serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all(), required=False, allow_null=True)
    root_cause_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all()),
        required=False,
        allow_empty=False,
    )
    title = serializers.CharField(allow_blank=False)
    description = serializers.CharField(allow_blank=False)
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    execution_date = serializers.DateField()
    status = serializers.ChoiceField(choices=TreatmentTaskStatus.choices, required=False, default=TreatmentTaskStatus.PENDING)


class TreatmentUpdateTaskSerializer(serializers.Serializer):
    root_cause = serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all(), required=False, allow_null=True)
    root_cause_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=TreatmentRootCause.objects.all()),
        required=False,
        allow_empty=False,
    )
    title = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    responsible = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)
    execution_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TreatmentTaskStatus.choices, required=False)
    evidence_note = serializers.CharField(required=False, allow_blank=True)


class TreatmentValidateSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=TreatmentEffectivenessValidationResult.choices, required=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class TreatmentLearnedLessonWriteSerializer(serializers.Serializer):
    has_learning = serializers.BooleanField(required=True)
    learned_text = serializers.CharField(required=False, allow_blank=True)
    no_learning_reason = serializers.CharField(required=False, allow_blank=True)
    procedure_modified = serializers.BooleanField(required=True)
    procedure_modification_notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        has_learning = attrs.get("has_learning")
        procedure_modified = attrs.get("procedure_modified")
        learned_text = (attrs.get("learned_text") or "").strip()
        no_learning_reason = (attrs.get("no_learning_reason") or "").strip()
        procedure_notes = (attrs.get("procedure_modification_notes") or "").strip()

        errors = {}
        if has_learning is True and not learned_text:
            errors["learned_text"] = "Debe completar que se aprendio."
        if has_learning is False and not no_learning_reason:
            errors["no_learning_reason"] = "Debe indicar por que no se aprendio."
        if procedure_modified is True and not procedure_notes:
            errors["procedure_modification_notes"] = "Debe completar las observaciones sobre modificacion de procedimiento."
        if errors:
            raise serializers.ValidationError(errors)

        attrs["learned_text"] = learned_text if has_learning else ""
        attrs["no_learning_reason"] = no_learning_reason if not has_learning else ""
        attrs["procedure_modification_notes"] = procedure_notes if procedure_modified else ""
        return attrs


class TreatmentEvidenceWriteSerializer(serializers.Serializer):
    file = serializers.FileField()
    note = serializers.CharField(required=False, allow_blank=True)
    original_name = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        return validate_evidence_file(value)


class TreatmentTaskEvidenceWriteSerializer(serializers.Serializer):
    file = serializers.FileField()
    note = serializers.CharField(required=False, allow_blank=True)
    original_name = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        return validate_evidence_file(value)


class TreatmentCandidateSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    current_status = serializers.CharField(read_only=True)
    current_stage = serializers.CharField(read_only=True)
    reporter = UserSummarySerializer(read_only=True)
    area = AnomalySectorSerializer(read_only=True)
    imputed_area = AnomalySectorSerializer(read_only=True)
    anomaly_origin = AnomalySectorSerializer(read_only=True)
    anomaly_type = AnomalySectorSerializer(read_only=True)
    severity = AnomalySectorSerializer(read_only=True)
    observation_resolution_path = serializers.CharField(read_only=True)
    suggested_by_repetition = serializers.SerializerMethodField()
    detected_at = serializers.DateTimeField(read_only=True)

    def get_suggested_by_repetition(self, obj):
        anchor = self.context.get("anchor_anomaly")
        if anchor is None:
            return False
        return bool(
            obj.anomaly_type_id == anchor.anomaly_type_id
            and (obj.imputed_area_id or obj.area_id) == (anchor.imputed_area_id or anchor.area_id)
        )


class TreatmentsApiRootSerializer(serializers.Serializer):
    treatments = serializers.CharField()
    candidates = serializers.CharField()

