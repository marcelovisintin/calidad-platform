"""Resolve the current owner and deadline of a pending email digest task."""

from django.utils import timezone

from apps.actions.models import ActionItem, Treatment, TreatmentTask
from apps.anomalies.models import Anomaly, ObservationAction
from apps.notifications.models import RecipientTaskStatus


def current_due_date(recipient):
    notification = recipient.notification
    if recipient.task_status != RecipientTaskStatus.PENDING:
        return None

    source_type = notification.source_type
    if source_type == "actions.actionitem":
        item = ActionItem.objects.filter(pk=notification.source_id).first()
        if item and item.status == "pending" and item.assigned_to_id == recipient.user_id:
            return item.due_date
    elif source_type == "actions.treatmenttask":
        task = TreatmentTask.objects.select_related("treatment").filter(pk=notification.source_id).first()
        if task and task.status == "pending" and task.responsible_id == recipient.user_id:
            if task.derived_from_lesson_id or task.treatment.status not in {"completed", "cancelled"}:
                return task.execution_date
    elif source_type == "anomalies.observationaction":
        action = ObservationAction.objects.select_related("anomaly", "anomaly__immediate_action").filter(
            pk=notification.source_id,
        ).first()
        if action and action.status == "pending" and action.anomaly.current_status not in {"closed", "cancelled"}:
            observation = getattr(action.anomaly, "immediate_action", None)
            if observation and observation.responsible_id == recipient.user_id:
                return action.estimated_completion_date
    elif source_type == "actions.treatment":
        treatment = Treatment.objects.filter(pk=notification.source_id).first()
        if not treatment:
            return None
        if notification.template_code == "treatment_effectiveness_assigned":
            if (treatment.effectiveness_responsible_id == recipient.user_id
                    and not treatment.effectiveness_validated_at
                    and treatment.status not in {"completed", "cancelled"}):
                return treatment.effectiveness_evaluation_date
        elif notification.template_code == "treatment_learned_lesson_assigned":
            if treatment.effectiveness_responsible_id == recipient.user_id:
                lesson = getattr(treatment, "learned_lesson", None)
                if not lesson or lesson.status != "published":
                    return timezone.localtime(notification.due_at).date() if notification.due_at else None
    elif source_type == "anomalies.anomaly":
        anomaly = Anomaly.objects.filter(pk=notification.source_id).first()
        if not anomaly or anomaly.current_status in {"closed", "cancelled"}:
            return None
        if notification.template_code == "observation_effectiveness_assigned":
            observation = getattr(anomaly, "immediate_action", None)
            if observation and observation.responsible_id == recipient.user_id and not observation.effectiveness_verified_at:
                return observation.effectiveness_due_at
        elif notification.template_code == "finding_management_assigned":
            treatment_id = notification.context_data.get("treatment_id")
            if treatment_id:
                treatment = Treatment.objects.filter(pk=treatment_id).first()
                if treatment and treatment.responsible_id == recipient.user_id and treatment.status == "pending":
                    return treatment.deadline
            elif notification.context_data.get("responsible_id") == str(recipient.user_id):
                observation = getattr(anomaly, "immediate_action", None)
                if observation:
                    return (
                        observation.action_date
                        if observation.responsible_id == recipient.user_id and not observation.action_completed_at
                        else None
                    )
                if anomaly.owner_id and anomaly.owner_id != recipient.user_id:
                    return None
                if anomaly.due_at:
                    return timezone.localtime(anomaly.due_at).date()
    return None
