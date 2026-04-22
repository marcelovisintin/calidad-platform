from django.contrib import admin

from apps.actions.models import (
    ActionEvidence,
    ActionItem,
    ActionItemHistory,
    ActionPlan,
    Treatment,
    TreatmentAnomaly,
    TreatmentEvidence,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentTask,
    TreatmentTaskAnomaly,
    TreatmentTaskEvidence,
)


class ActionEvidenceInline(admin.TabularInline):
    model = ActionEvidence
    extra = 0
    fields = ("evidence_type", "note", "file", "created_at")
    readonly_fields = ("created_at",)


class ActionItemHistoryInline(admin.TabularInline):
    model = ActionItemHistory
    extra = 0
    fields = ("event_type", "from_status", "to_status", "comment", "changed_by", "changed_at")
    readonly_fields = ("event_type", "from_status", "to_status", "comment", "changed_by", "changed_at")
    can_delete = False


class ActionItemInline(admin.TabularInline):
    model = ActionItem
    extra = 0
    fields = (
        "code",
        "title",
        "action_type",
        "priority",
        "assigned_to",
        "status",
        "due_date",
        "is_mandatory",
        "sequence",
    )


@admin.register(ActionPlan)
class ActionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "anomaly", "status", "owner", "approved_at", "created_at")
    list_filter = ("status", "approved_at")
    list_select_related = ("anomaly", "owner")
    search_fields = ("anomaly__code", "anomaly__title", "owner__username", "owner__email")
    readonly_fields = ("approved_at", "created_at", "updated_at", "row_version")
    inlines = [ActionItemInline]


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "action_plan",
        "status",
        "effective_status_display",
        "assigned_to",
        "priority",
        "due_date",
        "is_mandatory",
    )
    list_filter = ("status", "is_mandatory", "action_type", "priority")
    list_select_related = ("action_plan", "assigned_to", "action_type", "priority")
    search_fields = ("code", "title", "description", "action_plan__anomaly__code")
    readonly_fields = ("completed_at", "created_at", "updated_at", "row_version")
    inlines = [ActionEvidenceInline, ActionItemHistoryInline]

    @admin.display(description="Estado efectivo")
    def effective_status_display(self, obj):
        return obj.effective_status


@admin.register(ActionItemHistory)
class ActionItemHistoryAdmin(admin.ModelAdmin):
    list_display = ("action_item", "event_type", "from_status", "to_status", "changed_by", "changed_at")
    list_filter = ("event_type", "from_status", "to_status")
    list_select_related = ("action_item", "changed_by")
    search_fields = ("action_item__code", "action_item__title", "comment", "changed_by__username")
    readonly_fields = ("changed_at", "created_at", "updated_at", "row_version")


class TreatmentAnomalyInline(admin.TabularInline):
    model = TreatmentAnomaly
    extra = 0


class TreatmentParticipantInline(admin.TabularInline):
    model = TreatmentParticipant
    extra = 0


class TreatmentEvidenceInline(admin.TabularInline):
    model = TreatmentEvidence
    extra = 0
    fields = ("original_name", "content_type", "note", "file", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)


class TreatmentTaskInline(admin.TabularInline):
    model = TreatmentTask
    extra = 0
    fields = ("code", "title", "status", "responsible", "execution_date", "root_cause")


class TreatmentTaskEvidenceInline(admin.TabularInline):
    model = TreatmentTaskEvidence
    extra = 0
    fields = ("original_name", "content_type", "note", "file", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ("code", "primary_anomaly", "status", "scheduled_for", "method_used", "created_at")
    list_filter = ("status", "method_used")
    list_select_related = ("primary_anomaly",)
    search_fields = ("code", "primary_anomaly__code", "primary_anomaly__title")
    readonly_fields = ("created_at", "updated_at", "row_version")
    inlines = [TreatmentAnomalyInline, TreatmentParticipantInline, TreatmentEvidenceInline, TreatmentTaskInline]


@admin.register(TreatmentRootCause)
class TreatmentRootCauseAdmin(admin.ModelAdmin):
    list_display = ("treatment", "sequence", "description", "created_at")
    list_select_related = ("treatment",)
    search_fields = ("treatment__code", "description")


@admin.register(TreatmentTask)
class TreatmentTaskAdmin(admin.ModelAdmin):
    list_display = ("code", "treatment", "title", "status", "responsible", "execution_date")
    list_filter = ("status",)
    list_select_related = ("treatment", "responsible", "root_cause")
    search_fields = ("code", "title", "treatment__code")
    inlines = [TreatmentTaskEvidenceInline]


@admin.register(TreatmentTaskAnomaly)
class TreatmentTaskAnomalyAdmin(admin.ModelAdmin):
    list_display = ("task", "anomaly", "created_at")
    list_select_related = ("task", "anomaly")


@admin.register(TreatmentEvidence)
class TreatmentEvidenceAdmin(admin.ModelAdmin):
    list_display = ("treatment", "original_name", "uploaded_by", "created_at")
    list_select_related = ("treatment", "uploaded_by")
    search_fields = ("treatment__code", "original_name", "note")


@admin.register(TreatmentTaskEvidence)
class TreatmentTaskEvidenceAdmin(admin.ModelAdmin):
    list_display = ("treatment_task", "original_name", "uploaded_by", "created_at")
    list_select_related = ("treatment_task", "uploaded_by")
    search_fields = ("treatment_task__code", "original_name", "note")
