from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import AuditBaseModel
from common.storage import anomaly_attachment_upload_to


class AnomalyStatus(models.TextChoices):
    REGISTERED = "registered", "Registrada"
    IN_EVALUATION = "in_evaluation", "En evaluacion"
    IN_ANALYSIS = "in_analysis", "En analisis"
    IN_TREATMENT = "in_treatment", "En tratamiento"
    PENDING_VERIFICATION = "pending_verification", "Pendiente de verificacion"
    CLOSED = "closed", "Cerrada"
    CANCELLED = "cancelled", "Anulada"
    REOPENED = "reopened", "Reabierta"


class AnomalyStage(models.TextChoices):
    REGISTRATION = "registration", "Registro"
    CONTAINMENT = "containment", "Contencion"
    INITIAL_VERIFICATION = "initial_verification", "Verificacion inicial"
    CLASSIFICATION = "classification", "REVICION DE HALLAZGOS"
    TREATMENT_CREATED = "treatment_created", "Tratamiento creado"
    CAUSE_ANALYSIS = "cause_analysis", "Analisis de causa"
    PROPOSALS = "proposals", "Propuestas"
    ACTION_PLAN = "action_plan", "Plan de accion"
    EXECUTION_AND_FOLLOW_UP = "execution_follow_up", "Ejecucion y seguimiento"
    RESULTS = "results", "Resultados"
    EFFECTIVENESS_VERIFICATION = "effectiveness_verification", "Verificacion de eficacia"
    CLOSURE = "closure", "Cierre"
    STANDARDIZATION_AND_LEARNING = "standardization_learning", "Estandarizacion y aprendizaje"


STAGE_STATUS_MAP = {
    AnomalyStage.REGISTRATION: AnomalyStatus.REGISTERED,
    AnomalyStage.CONTAINMENT: AnomalyStatus.IN_EVALUATION,
    AnomalyStage.INITIAL_VERIFICATION: AnomalyStatus.IN_EVALUATION,
    AnomalyStage.CLASSIFICATION: AnomalyStatus.IN_EVALUATION,
    AnomalyStage.TREATMENT_CREATED: AnomalyStatus.IN_ANALYSIS,
    AnomalyStage.CAUSE_ANALYSIS: AnomalyStatus.IN_ANALYSIS,
    AnomalyStage.PROPOSALS: AnomalyStatus.IN_ANALYSIS,
    AnomalyStage.ACTION_PLAN: AnomalyStatus.IN_TREATMENT,
    AnomalyStage.EXECUTION_AND_FOLLOW_UP: AnomalyStatus.IN_TREATMENT,
    AnomalyStage.RESULTS: AnomalyStatus.IN_TREATMENT,
    AnomalyStage.EFFECTIVENESS_VERIFICATION: AnomalyStatus.PENDING_VERIFICATION,
    AnomalyStage.CLOSURE: AnomalyStatus.CLOSED,
    AnomalyStage.STANDARDIZATION_AND_LEARNING: AnomalyStatus.CLOSED,
}


class AnalysisMethod(models.TextChoices):
    FIVE_WHYS = "five_whys", "5 Why"
    ISHIKAWA = "ishikawa", "Ishikawa"
    A3 = "a3", "A3"
    EIGHT_D = "8d", "8D"
    PDCA = "pdca", "PDCA"
    OTHER = "other", "Otro"


class ParticipantRole(models.TextChoices):
    REPORTER = "reporter", "Registrador"
    OWNER = "owner", "Responsable"
    REVIEWER = "reviewer", "Evaluador"
    ANALYST = "analyst", "Analista"
    IMPLEMENTER = "implementer", "Implementador"
    VERIFIER = "verifier", "Verificador"
    OBSERVER = "observer", "Observador"


class AnomalyCommentType(models.TextChoices):
    GENERAL = "general", "General"
    CONTAINMENT = "containment", "Contencion"
    ANALYSIS = "analysis", "Analisis"
    RESULT = "result", "Resultado"
    CLOSURE = "closure", "Cierre"


class Anomaly(AuditBaseModel):
    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    current_status = models.CharField(
        max_length=40,
        choices=AnomalyStatus.choices,
        default=AnomalyStatus.REGISTERED,
    )
    current_stage = models.CharField(
        max_length=40,
        choices=AnomalyStage.choices,
        default=AnomalyStage.REGISTRATION,
    )
    site = models.ForeignKey("catalog.Site", on_delete=models.PROTECT, related_name="anomalies")
    area = models.ForeignKey("catalog.Area", on_delete=models.PROTECT, related_name="anomalies")
    line = models.ForeignKey(
        "catalog.Line",
        on_delete=models.PROTECT,
        related_name="anomalies",
        null=True,
        blank=True,
    )
    reporter = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="reported_anomalies",
    )
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="owned_anomalies",
        null=True,
        blank=True,
    )
    anomaly_type = models.ForeignKey("catalog.AnomalyType", on_delete=models.PROTECT, related_name="anomalies")
    anomaly_origin = models.ForeignKey(
        "catalog.AnomalyOrigin",
        on_delete=models.PROTECT,
        related_name="anomalies",
    )
    severity = models.ForeignKey("catalog.Severity", on_delete=models.PROTECT, related_name="anomalies", null=True, blank=True)
    priority = models.ForeignKey("catalog.Priority", on_delete=models.PROTECT, related_name="anomalies")
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="duplicates",
        null=True,
        blank=True,
    )
    detected_at = models.DateTimeField()
    manufacturing_order_number = models.CharField(max_length=50, blank=True)
    affected_quantity = models.PositiveIntegerField(null=True, blank=True)
    affected_process = models.CharField(max_length=255, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_transition_at = models.DateTimeField(null=True, blank=True)
    containment_summary = models.TextField(blank=True)
    classification_summary = models.TextField(blank=True)
    classification_change_count = models.PositiveIntegerField(default=0)
    classification_change_unlocked = models.BooleanField(default=False)
    root_cause_summary = models.TextField(blank=True)
    resolution_summary = models.TextField(blank=True)
    result_summary = models.TextField(blank=True)
    effectiveness_summary = models.TextField(blank=True)
    closure_comment = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    reopened_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-detected_at", "code")
        indexes = [
            models.Index(fields=["current_status", "current_stage", "area"], name="anom_stat_stage_area_idx"),
            models.Index(fields=["code"], name="anom_code_idx"),
            models.Index(fields=["detected_at"], name="anom_detected_idx"),
        ]
        verbose_name = "Anomalia"
        verbose_name_plural = "Anomalias"

    def clean(self):
        if self.closed_at and self.current_status != AnomalyStatus.CLOSED:
            raise ValidationError({"closed_at": "closed_at solo puede informarse cuando el estado es closed."})
        if self.area_id and self.area and self.area.site_id != self.site_id:
            raise ValidationError({"area": "El area seleccionada no pertenece al sitio indicado."})
        if self.line_id and self.line and self.line.area_id != self.area_id:
            raise ValidationError({"line": "La linea seleccionada no pertenece al area indicada."})
        if self.current_status not in {AnomalyStatus.CANCELLED, AnomalyStatus.REOPENED}:
            expected_status = STAGE_STATUS_MAP.get(self.current_stage)
            if expected_status and expected_status != self.current_status:
                raise ValidationError(
                    {"current_stage": "La etapa seleccionada no coincide con el estado actual de la anomalia."}
                )

    def __str__(self) -> str:
        return f"{self.code} - {self.title}"


class AnomalyCodeReservation(AuditBaseModel):
    code = models.CharField(max_length=50, unique=True)
    year = models.PositiveIntegerField()
    sequence = models.PositiveIntegerField()
    reserved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_code_reservations",
    )
    anomaly = models.OneToOneField(
        "anomalies.Anomaly",
        on_delete=models.SET_NULL,
        related_name="code_reservation",
        null=True,
        blank=True,
    )
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_code_reservations_consumed",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["year", "sequence"], name="anom_code_resv_year_seq_idx"),
            models.Index(fields=["reserved_by", "consumed_at"], name="anom_code_resv_user_cons_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="anom_code_resv_year_seq_uq"),
        ]
        verbose_name = "Reserva de codigo de anomalia"
        verbose_name_plural = "Reservas de codigos de anomalia"

    def __str__(self) -> str:
        return self.code


class AnomalyStatusHistory(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=40, choices=AnomalyStatus.choices)
    to_status = models.CharField(max_length=40, choices=AnomalyStatus.choices)
    from_stage = models.CharField(max_length=40, choices=AnomalyStage.choices)
    to_stage = models.CharField(max_length=40, choices=AnomalyStage.choices)
    comment = models.TextField()
    changed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_status_changes",
    )
    changed_at = models.DateTimeField()

    class Meta:
        ordering = ("-changed_at", "-created_at")
        verbose_name = "Historial de estado"
        verbose_name_plural = "Historial de estados"


class AnomalyComment(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="comments")
    body = models.TextField()
    comment_type = models.CharField(max_length=20, choices=AnomalyCommentType.choices, default=AnomalyCommentType.GENERAL)
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="anomaly_comments")

    class Meta:
        ordering = ("created_at",)
        verbose_name = "Comentario de anomalia"
        verbose_name_plural = "Comentarios de anomalia"


class AnomalyAttachment(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=anomaly_attachment_upload_to)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_attachments",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Adjunto de anomalia"
        verbose_name_plural = "Adjuntos de anomalia"


class AnomalyParticipant(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="anomaly_participations")
    role = models.CharField(max_length=30, choices=ParticipantRole.choices)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("role", "created_at")
        verbose_name = "Participante de anomalia"
        verbose_name_plural = "Participantes de anomalia"
        constraints = [
            models.UniqueConstraint(fields=["anomaly", "user", "role"], name="anom_part_usr_role_uq")
        ]

    def __str__(self) -> str:
        return f"{self.anomaly.code} | {self.user} | {self.role}"


class AnomalyInitialVerification(AuditBaseModel):
    anomaly = models.OneToOneField("anomalies.Anomaly", on_delete=models.CASCADE, related_name="initial_verification")
    verified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="initial_verifications",
    )
    verified_at = models.DateTimeField()
    material_checked = models.BooleanField(default=False)
    machine_checked = models.BooleanField(default=False)
    method_checked = models.BooleanField(default=False)
    manpower_checked = models.BooleanField(default=False)
    milieu_checked = models.BooleanField(default=False)
    measurement_checked = models.BooleanField(default=False)
    material_notes = models.TextField(blank=True)
    machine_notes = models.TextField(blank=True)
    method_notes = models.TextField(blank=True)
    manpower_notes = models.TextField(blank=True)
    milieu_notes = models.TextField(blank=True)
    measurement_notes = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name = "Verificacion inicial"
        verbose_name_plural = "Verificaciones iniciales"


class AnomalyClassification(AuditBaseModel):
    anomaly = models.OneToOneField("anomalies.Anomaly", on_delete=models.CASCADE, related_name="classification")
    classified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_classifications",
    )
    classified_at = models.DateTimeField()
    containment_required = models.BooleanField(default=True)
    requires_action_plan = models.BooleanField(default=True)
    requires_effectiveness_verification = models.BooleanField(default=True)
    impact_scope = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name = "REVICION DE HALLAZGOS de anomalia"
        verbose_name_plural = "REVICION DE HALLAZGOS de anomalia"


class AnomalyCauseAnalysis(AuditBaseModel):
    anomaly = models.OneToOneField("anomalies.Anomaly", on_delete=models.CASCADE, related_name="cause_analysis")
    analyzed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_cause_analyses",
    )
    analyzed_at = models.DateTimeField()
    method_used = models.CharField(max_length=30, choices=AnalysisMethod.choices)
    immediate_cause = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name = "Analisis de causa"
        verbose_name_plural = "Analisis de causa"


class AnomalyProposal(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="proposals")
    title = models.CharField(max_length=255)
    description = models.TextField()
    proposed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_proposals",
    )
    proposed_at = models.DateTimeField()
    is_selected = models.BooleanField(default=False)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "created_at")
        verbose_name = "Propuesta"
        verbose_name_plural = "Propuestas"
        constraints = [
            models.UniqueConstraint(fields=["anomaly", "sequence"], name="anom_prop_seq_uq")
        ]

    def __str__(self) -> str:
        return f"{self.anomaly.code} - {self.title}"


class AnomalyEffectivenessCheck(AuditBaseModel):
    anomaly = models.ForeignKey("anomalies.Anomaly", on_delete=models.CASCADE, related_name="effectiveness_checks")
    verified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_effectiveness_checks",
    )
    verified_at = models.DateTimeField()
    is_effective = models.BooleanField()
    evidence_summary = models.TextField(blank=True)
    comment = models.TextField()
    recommended_stage = models.CharField(
        max_length=40,
        choices=AnomalyStage.choices,
        blank=True,
    )

    class Meta:
        ordering = ("-verified_at", "-created_at")
        verbose_name = "Verificacion de eficacia"
        verbose_name_plural = "Verificaciones de eficacia"

    def clean(self):
        if self.is_effective and self.recommended_stage:
            raise ValidationError(
                {"recommended_stage": "No corresponde informar una etapa sugerida cuando la verificacion fue eficaz."}
            )


class AnomalyLearning(AuditBaseModel):
    anomaly = models.OneToOneField("anomalies.Anomaly", on_delete=models.CASCADE, related_name="learning")
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_learning_records",
    )
    recorded_at = models.DateTimeField()
    standardization_actions = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    document_changes = models.TextField(blank=True)
    shared_with = models.TextField(blank=True)
    shared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Estandarizacion y aprendizaje"
        verbose_name_plural = "Estandarizacion y aprendizaje"



class AnomalyImmediateAction(AuditBaseModel):
    anomaly = models.OneToOneField("anomalies.Anomaly", on_delete=models.CASCADE, related_name="immediate_action")
    responsible = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="anomaly_immediate_actions",
    )
    action_date = models.DateField()
    effectiveness_verified_at = models.DateTimeField()
    observation = models.TextField()
    actions_taken = models.TextField()
    effectiveness_comment = models.TextField(blank=True)
    closure_comment = models.TextField(blank=True)

    class Meta:
        verbose_name = "Accion inmediata de anomalia"
        verbose_name_plural = "Acciones inmediatas de anomalia"

