from __future__ import annotations

from collections import OrderedDict

from django.db.models import Q
from django.utils import timezone

from apps.accounts.constants import (
    PERMISSION_ADD_USER,
    PERMISSION_CHANGE_USER,
    PERMISSION_VIEW_AUDIT,
    ROLE_ADMINISTRADOR,
)
from apps.accounts.models import User
from apps.actions.models import ActionItem, ActionItemStatus, Treatment, TreatmentStatus, TreatmentTask, TreatmentTaskStatus
from apps.anomalies.models import Anomaly, AnomalyStatus


ADMIN_DASHBOARD_PERMISSIONS = {
    PERMISSION_ADD_USER,
    PERMISSION_CHANGE_USER,
    PERMISSION_VIEW_AUDIT,
}

ANOMALY_STATUS_LABELS = OrderedDict(
    [
        ("overdue", "Vencidas"),
        (AnomalyStatus.REGISTERED, "Registradas"),
        (AnomalyStatus.IN_EVALUATION, "En evaluacion"),
        (AnomalyStatus.IN_ANALYSIS, "En analisis"),
        (AnomalyStatus.IN_TREATMENT, "En tratamiento"),
        (AnomalyStatus.PENDING_VERIFICATION, "Pendientes de verificacion"),
        (AnomalyStatus.CLOSED, "Cerradas"),
        (AnomalyStatus.CANCELLED, "Anuladas"),
        (AnomalyStatus.REOPENED, "Reabiertas"),
    ]
)

ACTION_STATUS_LABELS = OrderedDict(
    [
        ("overdue", "Vencidas"),
        (ActionItemStatus.PENDING, "Pendientes"),
        (ActionItemStatus.IN_PROGRESS, "En curso"),
        (ActionItemStatus.COMPLETED, "Completadas"),
        (ActionItemStatus.CANCELLED, "Canceladas"),
    ]
)

TREATMENT_STATUS_LABELS = OrderedDict(
    [
        (TreatmentStatus.PENDING, "Abiertos"),
        (TreatmentStatus.SCHEDULED, "Programados"),
        (TreatmentStatus.IN_PROGRESS, "En tratamiento"),
        (TreatmentStatus.COMPLETED, "Cerrados"),
        (TreatmentStatus.CANCELLED, "Cancelados"),
    ]
)


def _is_dashboard_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    access_level = (getattr(user, "access_level", "") or "").lower()
    if access_level in {"administrador", "desarrollador"}:
        return True
    if user.role_scopes.filter(role__code__iexact=ROLE_ADMINISTRADOR).exists():
        return True
    return any(user.has_perm(permission) for permission in ADMIN_DASHBOARD_PERMISSIONS)


def _user_label(user: User) -> str:
    return user.full_name or user.username or user.email


def _status_rows(labels: OrderedDict, counts: dict[str, int]) -> list[dict]:
    return [
        {"key": key, "label": label, "count": counts.get(key, 0)}
        for key, label in labels.items()
    ]


def _anomaly_queryset_for_user(user):
    return Anomaly.objects.filter(
        Q(reporter=user)
        | Q(owner=user)
        | Q(created_by=user)
        | Q(updated_by=user)
        | Q(participants__user=user)
    ).distinct()


def _action_queryset_for_user(user):
    return ActionItem.objects.filter(
        Q(assigned_to=user)
        | Q(created_by=user)
        | Q(updated_by=user)
        | Q(history__changed_by=user)
    ).distinct()


def _treatment_task_queryset_for_user(user):
    return TreatmentTask.objects.filter(responsible=user).distinct()


def _treatment_queryset_for_user(user):
    return Treatment.objects.filter(
        Q(created_by=user)
        | Q(updated_by=user)
        | Q(participants__user=user)
        | Q(effectiveness_responsible=user)
        | Q(effectiveness_validated_by=user)
        | Q(tasks__responsible=user)
    ).distinct()


def _count_anomalies(queryset):
    today = timezone.localdate()
    overdue = queryset.filter(
        due_at__date__lt=today,
    ).exclude(current_status__in=[AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED]).count()
    counts = {"overdue": overdue}
    for status in AnomalyStatus.values:
        status_queryset = queryset.filter(current_status=status)
        if status not in {AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED}:
            status_queryset = status_queryset.exclude(due_at__date__lt=today)
        counts[status] = status_queryset.count()
    return counts


def _count_actions(queryset):
    today = timezone.localdate()
    overdue = queryset.filter(
        status__in=[ActionItemStatus.PENDING, ActionItemStatus.IN_PROGRESS],
        due_date__lt=today,
    ).count()
    counts = {"overdue": overdue}
    for status in ActionItemStatus.values:
        status_queryset = queryset.filter(status=status)
        if status in {ActionItemStatus.PENDING, ActionItemStatus.IN_PROGRESS}:
            status_queryset = status_queryset.exclude(due_date__lt=today)
        counts[status] = status_queryset.count()
    return counts


def _count_treatment_tasks(queryset):
    today = timezone.localdate()
    overdue = queryset.filter(
        status__in=[TreatmentTaskStatus.PENDING, TreatmentTaskStatus.IN_PROGRESS],
        execution_date__lt=today,
    ).count()
    counts = {"overdue": overdue}
    for status in TreatmentTaskStatus.values:
        status_queryset = queryset.filter(status=status)
        if status in {TreatmentTaskStatus.PENDING, TreatmentTaskStatus.IN_PROGRESS}:
            status_queryset = status_queryset.exclude(execution_date__lt=today)
        counts[status] = status_queryset.count()
    return counts


def _combine_counts(*count_groups):
    combined = {}
    for counts in count_groups:
        for key, value in counts.items():
            combined[key] = combined.get(key, 0) + value
    return combined


def _count_action_work(querysets):
    action_queryset, task_queryset = querysets
    return _combine_counts(_count_actions(action_queryset), _count_treatment_tasks(task_queryset))


def _count_treatments(queryset):
    return {status: queryset.filter(status=status).count() for status in TreatmentStatus.values}


def _user_detail_rows(*, users, queryset_factory, counter, labels):
    rows = []
    for user in users:
        queryset = queryset_factory(user)
        total = queryset.count()
        rows.append(
            {
                "user": {
                    "id": str(user.pk),
                    "name": _user_label(user),
                    "username": user.username,
                },
                "total": total,
                "statuses": _status_rows(labels, counter(queryset)),
            }
        )
    return rows


def _user_action_detail_rows(*, users):
    rows = []
    for user in users:
        action_queryset = _action_queryset_for_user(user)
        task_queryset = _treatment_task_queryset_for_user(user)
        total = action_queryset.count() + task_queryset.count()
        rows.append(
            {
                "user": {
                    "id": str(user.pk),
                    "name": _user_label(user),
                    "username": user.username,
                },
                "total": total,
                "statuses": _status_rows(ACTION_STATUS_LABELS, _count_action_work((action_queryset, task_queryset))),
            }
        )
    return rows


def _card(*, key, title, description, queryset, labels, counter, detail_rows=None):
    counts = counter(queryset)
    payload = {
        "key": key,
        "title": title,
        "description": description,
        "total": queryset.count(),
        "statuses": _status_rows(labels, counts),
    }
    if detail_rows is not None:
        payload["detail_rows"] = detail_rows
    return payload


def _actions_card(*, description, action_queryset, task_queryset, detail_rows=None):
    counts = _count_action_work((action_queryset, task_queryset))
    payload = {
        "key": "actions",
        "title": "Acciones",
        "description": description,
        "total": action_queryset.count() + task_queryset.count(),
        "statuses": _status_rows(ACTION_STATUS_LABELS, counts),
    }
    if detail_rows is not None:
        payload["detail_rows"] = detail_rows
    return payload


def dashboard_summary_for_user(user) -> dict:
    is_admin = _is_dashboard_admin(user)
    users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username") if is_admin else []

    anomaly_queryset = Anomaly.objects.all() if is_admin else _anomaly_queryset_for_user(user)
    action_queryset = ActionItem.objects.all() if is_admin else _action_queryset_for_user(user)
    task_queryset = TreatmentTask.objects.all() if is_admin else _treatment_task_queryset_for_user(user)
    treatment_queryset = Treatment.objects.all() if is_admin else _treatment_queryset_for_user(user)

    anomaly_detail = None
    action_detail = None
    treatment_detail = None
    if is_admin:
        anomaly_detail = _user_detail_rows(
            users=users,
            queryset_factory=_anomaly_queryset_for_user,
            counter=_count_anomalies,
            labels=ANOMALY_STATUS_LABELS,
        )
        action_detail = _user_action_detail_rows(users=users)
        treatment_detail = _user_detail_rows(
            users=users,
            queryset_factory=_treatment_queryset_for_user,
            counter=_count_treatments,
            labels=TREATMENT_STATUS_LABELS,
        )

    return {
        "scope": "admin" if is_admin else "user",
        "cards": [
            _card(
                key="anomalies",
                title="Seguimiento de anomalias",
                description="Total historico general" if is_admin else "Total historico reportado por vos",
                queryset=anomaly_queryset,
                labels=ANOMALY_STATUS_LABELS,
                counter=_count_anomalies,
                detail_rows=anomaly_detail,
            ),
            _actions_card(
                description="Total historico general" if is_admin else "Total historico de acciones asignadas",
                action_queryset=action_queryset,
                task_queryset=task_queryset,
                detail_rows=action_detail,
            ),
            _card(
                key="treatments",
                title="Tratamientos",
                description="Total historico general" if is_admin else "Tratamientos vinculados a vos",
                queryset=treatment_queryset,
                labels=TREATMENT_STATUS_LABELS,
                counter=_count_treatments,
                detail_rows=treatment_detail,
            ),
        ],
    }
