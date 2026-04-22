from django.contrib import admin

from apps.anomalies.models import (
    Anomaly,
    AnomalyAttachment,
    AnomalyCauseAnalysis,
    AnomalyClassification,
    AnomalyCodeReservation,
    AnomalyComment,
    AnomalyEffectivenessCheck,
    AnomalyInitialVerification,
    AnomalyImmediateAction,
    AnomalyLearning,
    AnomalyParticipant,
    AnomalyProposal,
    AnomalyStatusHistory,
)


class AnomalyCommentInline(admin.TabularInline):
    model = AnomalyComment
    extra = 0
    readonly_fields = ("author", "created_at")


class AnomalyAttachmentInline(admin.TabularInline):
    model = AnomalyAttachment
    extra = 0
    readonly_fields = ("uploaded_by", "created_at")


class AnomalyParticipantInline(admin.TabularInline):
    model = AnomalyParticipant
    extra = 0


class AnomalyProposalInline(admin.TabularInline):
    model = AnomalyProposal
    extra = 0
    readonly_fields = ("proposed_by", "proposed_at", "created_at")


class AnomalyStatusHistoryInline(admin.TabularInline):
    model = AnomalyStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "from_stage", "to_stage", "comment", "changed_by", "changed_at")


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "current_status",
        "current_stage",
        "site",
        "area",
        "manufacturing_order_number",
        "affected_quantity",
        "priority",
        "owner",
        "detected_at",
    )
    list_filter = ("current_status", "current_stage", "site", "area", "severity", "priority")
    list_select_related = (
        "site",
        "area",
        "line",
        "priority",
        "severity",
        "owner",
        "reporter",
        "anomaly_type",
        "anomaly_origin",
    )
    search_fields = ("code", "title", "description", "manufacturing_order_number", "affected_process")
    readonly_fields = ("code", "current_status", "current_stage", "closed_at", "last_transition_at", "reopened_count")
    inlines = [
        AnomalyCommentInline,
        AnomalyAttachmentInline,
        AnomalyParticipantInline,
        AnomalyProposalInline,
        AnomalyStatusHistoryInline,
    ]


@admin.register(AnomalyInitialVerification)
class AnomalyInitialVerificationAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "verified_by", "verified_at")
    list_select_related = ("anomaly", "verified_by")
    search_fields = ("anomaly__code", "verified_by__username", "summary")


@admin.register(AnomalyClassification)
class AnomalyClassificationAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "classified_by", "classified_at", "requires_action_plan")
    list_select_related = ("anomaly", "classified_by")
    search_fields = ("anomaly__code", "classified_by__username", "summary")


@admin.register(AnomalyCauseAnalysis)
class AnomalyCauseAnalysisAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "analyzed_by", "analyzed_at", "method_used")
    list_select_related = ("anomaly", "analyzed_by")
    search_fields = ("anomaly__code", "analyzed_by__username", "root_cause", "summary")


@admin.register(AnomalyEffectivenessCheck)
class AnomalyEffectivenessCheckAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "verified_by", "verified_at", "is_effective", "recommended_stage")
    list_select_related = ("anomaly", "verified_by")
    list_filter = ("is_effective", "recommended_stage")
    search_fields = ("anomaly__code", "verified_by__username", "comment")


@admin.register(AnomalyLearning)
class AnomalyLearningAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "recorded_by", "recorded_at", "shared_at")
    list_select_related = ("anomaly", "recorded_by")
    search_fields = ("anomaly__code", "recorded_by__username", "lessons_learned")



@admin.register(AnomalyImmediateAction)
class AnomalyImmediateActionAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "responsible", "action_date", "effectiveness_verified_at")
    list_select_related = ("anomaly", "responsible")
    search_fields = ("anomaly__code", "responsible__username", "observation", "actions_taken")


@admin.register(AnomalyCodeReservation)
class AnomalyCodeReservationAdmin(admin.ModelAdmin):
    list_display = ("code", "reserved_by", "anomaly", "created_at", "consumed_at")
    list_select_related = ("reserved_by", "anomaly", "consumed_by")
    search_fields = ("code", "reserved_by__username", "anomaly__code")
    readonly_fields = ("code", "year", "sequence", "reserved_by", "anomaly", "consumed_at", "consumed_by", "created_at", "updated_at")

@admin.register(AnomalyStatusHistory)
class AnomalyStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "from_status", "to_status", "from_stage", "to_stage", "changed_by", "changed_at")
    list_select_related = ("anomaly", "changed_by")
    search_fields = ("anomaly__code", "changed_by__username", "comment")


@admin.register(AnomalyComment)
class AnomalyCommentAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "comment_type", "author", "created_at")
    list_select_related = ("anomaly", "author")
    search_fields = ("anomaly__code", "author__username", "body")


@admin.register(AnomalyAttachment)
class AnomalyAttachmentAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "original_name", "uploaded_by", "created_at")
    list_select_related = ("anomaly", "uploaded_by")
    search_fields = ("anomaly__code", "original_name", "uploaded_by__username")


@admin.register(AnomalyParticipant)
class AnomalyParticipantAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "user", "role", "created_at")
    list_select_related = ("anomaly", "user")
    list_filter = ("role",)
    search_fields = ("anomaly__code", "user__username", "note")


@admin.register(AnomalyProposal)
class AnomalyProposalAdmin(admin.ModelAdmin):
    list_display = ("anomaly", "sequence", "title", "proposed_by", "is_selected", "proposed_at")
    list_select_related = ("anomaly", "proposed_by")
    list_filter = ("is_selected",)
    search_fields = ("anomaly__code", "title", "description", "proposed_by__username")


