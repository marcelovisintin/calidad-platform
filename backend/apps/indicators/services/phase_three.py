from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.actions.models import (
    ActionItem,
    ActionItemStatus,
    Treatment,
    TreatmentEffectivenessValidationResult,
    TreatmentLearnedLesson,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskStatus,
)
from apps.anomalies.models import AffectedOrder, Anomaly, AnomalyImmediateAction, ObservationResolutionPath
from apps.indicators.services.phase_two import (
    MONTH_LABELS,
    _anomaly_base,
    _base_payload,
    _comparison,
    _month_starts,
    _paged_rows,
    _parse_area_id,
    _parse_period,
    _safe_percentage,
)


PHASE_THREE_KEYS = {
    "finding-classification",
    "repetition-pareto",
    "actions",
    "effectiveness",
    "affected-orders",
    "learned-lessons",
}
REPETITION_DIMENSIONS = {
    "process_type",
    "process",
    "type",
    "origin",
    "classification",
    "order",
}


def _local_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _in_period(value, period) -> bool:
    normalized = _local_date(value)
    return bool(normalized and period.date_from <= normalized <= period.date_to)


def _month_key(value) -> date | None:
    normalized = _local_date(value)
    return date(normalized.year, normalized.month, 1) if normalized else None


def _user_name(user) -> str:
    return user.full_name if user else "Sin responsable"


def _series(period, monthly: dict[date, dict[str, int]], labels: dict[str, str]) -> list[dict]:
    result = []
    for month in _month_starts(period.date_from, period.date_to):
        values = monthly.get(month, {})
        total = sum(values.values())
        result.append(
            {
                "period": month.isoformat(),
                "label": f"{MONTH_LABELS[month.month - 1]} {month.year}",
                "values": [
                    {
                        "key": key,
                        "label": label,
                        "count": values.get(key, 0),
                        "percentage": _safe_percentage(values.get(key, 0), total),
                    }
                    for key, label in labels.items()
                ],
            }
        )
    return result


def _breakdown(counts: dict[str, int], labels: dict[str, str], *, denominator: int | None = None) -> list[dict]:
    total = sum(counts.values()) if denominator is None else denominator
    return [
        {"key": key, "label": labels.get(key, key), "count": count, "percentage": _safe_percentage(count, total)}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], labels.get(item[0], item[0])))
    ]


def _classification_key(anomaly) -> tuple[str, str]:
    if anomaly.severity_id is None:
        return "unclassified", "Sin clasificar"
    if anomaly.observation_resolution_path in {
        ObservationResolutionPath.TREATMENT_PENDING,
        ObservationResolutionPath.TREATMENT,
    }:
        return "observation_trt", "Observacion TRT"
    return str(anomaly.severity_id), anomaly.severity.name


def _classification_dashboard(params, period, area_id) -> dict:
    base = _anomaly_base(area_id).select_related("classification")
    current = list(
        base.filter(
            Q(classification__classified_at__date__range=(period.date_from, period.date_to))
            | Q(severity__isnull=True, detected_at__date__range=(period.date_from, period.date_to))
        ).order_by("-detected_at", "code")
    )
    previous = list(
        base.filter(
            Q(classification__classified_at__date__range=(period.previous_from, period.previous_to))
            | Q(severity__isnull=True, detected_at__date__range=(period.previous_from, period.previous_to))
        )
    )
    counts: dict[str, int] = defaultdict(int)
    labels: dict[str, str] = {}
    previous_counts: dict[str, int] = defaultdict(int)
    monthly: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for anomaly in current:
        key, label = _classification_key(anomaly)
        counts[key] += 1
        labels[key] = label
        classified_at = getattr(getattr(anomaly, "classification", None), "classified_at", None)
        month = _month_key(classified_at or anomaly.detected_at)
        monthly[month][key] += 1
    for anomaly in previous:
        key, _ = _classification_key(anomaly)
        previous_counts[key] += 1
    total = len(current)
    rows = [
        {
            "id": str(anomaly.pk),
            "code": anomaly.code,
            "title": anomaly.title,
            "process": anomaly.area.name,
            "classification": _classification_key(anomaly)[1],
            "classified_at": (
                getattr(getattr(anomaly, "classification", None), "classified_at", None) or anomaly.detected_at
            ).isoformat(),
            "status": anomaly.get_current_status_display(),
            "detail_url": f"/anomalies/{anomaly.pk}",
        }
        for anomaly in current
    ]
    breakdown = _breakdown(counts, labels)
    for item in breakdown:
        item["comparison"] = _comparison(item["count"], previous_counts.get(item["key"], 0))
    top = breakdown[0] if breakdown else None
    payload = _base_payload("finding-classification", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "La clasificacion utiliza el maestro de Revision de hallazgos; no hay nombres de categorias fijados en el indicador.",
                "Las observaciones derivadas a tratamiento se muestran separadas como Observacion TRT sin perder su clasificacion original.",
                "Los casos aun sin revision se incorporan por fecha de deteccion para que no queden ocultos.",
            ],
            "metrics": [
                {"key": "total", "label": "Hallazgos del periodo", "value": total, "percentage": None, "tone": "accent", "comparison": _comparison(total, len(previous))},
                {"key": "classified", "label": "Clasificados", "value": total - counts.get("unclassified", 0), "percentage": _safe_percentage(total - counts.get("unclassified", 0), total), "tone": "success", "comparison": None},
                {"key": "unclassified", "label": "Sin clasificar", "value": counts.get("unclassified", 0), "percentage": _safe_percentage(counts.get("unclassified", 0), total), "tone": "warning", "comparison": None},
                {"key": "top", "label": "Clasificacion principal", "value": top["count"] if top else 0, "percentage": top["percentage"] if top else None, "tone": "default", "hint": top["label"] if top else "Sin datos", "comparison": top.get("comparison") if top else None},
            ],
            "series": _series(period, monthly, labels),
            "breakdown": breakdown,
            "rows": _paged_rows(rows, params, lambda item: item),
        }
    )
    return payload


def _repetition_group(anomaly, dimension: str) -> list[tuple[str, str]]:
    if dimension == "process":
        return [(str(anomaly.area_id), f"{anomaly.area.code} - {anomaly.area.name}")]
    if dimension == "type":
        return [(str(anomaly.anomaly_type_id), anomaly.anomaly_type.name)]
    if dimension == "origin":
        return [(str(anomaly.anomaly_origin_id), anomaly.anomaly_origin.name)]
    if dimension == "classification":
        return [_classification_key(anomaly)]
    if dimension == "order":
        return [
            (f"{item.order_type_id}:{item.number.strip().upper()}", f"{item.order_type.code} {item.number}")
            for item in anomaly.affected_orders.all()
        ] or [("without_order", "Sin orden afectada")]
    return [
        (
            f"{anomaly.area_id}:{anomaly.anomaly_type_id}",
            f"{anomaly.area.name} / {anomaly.anomaly_type.name}",
        )
    ]


def _repetition_dashboard(params, period, area_id) -> dict:
    dimension = (params.get("group_by") or "process_type").strip()
    if dimension not in REPETITION_DIMENSIONS:
        raise ValidationError({"group_by": "La agrupacion seleccionada no es valida."})
    current = list(
        _anomaly_base(area_id)
        .select_related("anomaly_type", "anomaly_origin")
        .prefetch_related("affected_orders__order_type")
        .filter(detected_at__date__range=(period.date_from, period.date_to))
        .order_by("-detected_at", "code")
    )
    previous = list(
        _anomaly_base(area_id)
        .select_related("anomaly_type", "anomaly_origin")
        .prefetch_related("affected_orders__order_type")
        .filter(detected_at__date__range=(period.previous_from, period.previous_to))
    )
    groups: dict[str, dict] = {}
    previous_counts: dict[str, int] = defaultdict(int)
    monthly: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for anomaly in current:
        for key, label in _repetition_group(anomaly, dimension):
            group = groups.setdefault(key, {"label": label, "anomaly_ids": set(), "codes": []})
            if anomaly.pk not in group["anomaly_ids"]:
                group["anomaly_ids"].add(anomaly.pk)
                group["codes"].append(anomaly.code)
                monthly[_month_key(anomaly.detected_at)][key] += 1
    for anomaly in previous:
        for key, _ in _repetition_group(anomaly, dimension):
            previous_counts[key] += 1
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]["anomaly_ids"]), item[1]["label"]))
    denominator = sum(len(group["anomaly_ids"]) for _, group in ordered)
    cumulative = 0
    rows = []
    breakdown = []
    labels = {}
    for key, group in ordered:
        count = len(group["anomaly_ids"])
        cumulative += count
        percentage = _safe_percentage(count, denominator)
        cumulative_percentage = _safe_percentage(cumulative, denominator)
        labels[key] = group["label"]
        item = {
            "key": key,
            "label": group["label"],
            "count": count,
            "percentage": percentage,
            "cumulative_percentage": cumulative_percentage,
            "comparison": _comparison(count, previous_counts.get(key, 0)),
        }
        breakdown.append(item)
        rows.append(
            {
                "id": key,
                "group": group["label"],
                "count": count,
                "percentage": percentage,
                "cumulative_percentage": cumulative_percentage,
                "previous": previous_counts.get(key, 0),
                "delta": count - previous_counts.get(key, 0),
                "cases": ", ".join(group["codes"][:8]) + ("..." if len(group["codes"]) > 8 else ""),
                "detail_url": "/anomalies",
            }
        )
    top = breakdown[0] if breakdown else None
    payload = _base_payload("repetition-pareto", period, area_id=area_id)
    payload["filters"]["group_by"] = dimension
    payload.update(
        {
            "formula_notes": [
                "La repetitividad se agrupa por la dimension seleccionada y cada anomalia se cuenta una vez dentro de cada grupo.",
                "El porcentaje acumulado permite identificar el conjunto que concentra aproximadamente el 80 por ciento de los casos.",
                "En Orden afectada una anomalia puede integrar mas de un grupo si afecto ordenes diferentes.",
            ],
            "metrics": [
                {"key": "anomalies", "label": "Anomalias analizadas", "value": len(current), "percentage": None, "tone": "accent", "comparison": _comparison(len(current), len(previous))},
                {"key": "groups", "label": "Grupos con casos", "value": len(groups), "percentage": None, "tone": "default", "comparison": None},
                {"key": "repeated", "label": "Grupos repetidos", "value": sum(1 for group in groups.values() if len(group["anomaly_ids"]) > 1), "percentage": _safe_percentage(sum(1 for group in groups.values() if len(group["anomaly_ids"]) > 1), len(groups)), "tone": "warning", "comparison": None},
                {"key": "top", "label": "Mayor concentracion", "value": top["count"] if top else 0, "percentage": top["percentage"] if top else None, "tone": "warning", "hint": top["label"] if top else "Sin datos", "comparison": top.get("comparison") if top else None},
            ],
            "series": _series(period, monthly, labels),
            "breakdown": breakdown,
            "rows": _paged_rows(rows, params, lambda item: item),
        }
    )
    return payload


def _action_records(period, area_id) -> list[dict]:
    direct = ActionItem.objects.select_related(
        "action_plan__anomaly__area", "assigned_to", "action_type"
    ).filter(created_at__date__range=(period.date_from, period.date_to))
    treatment = TreatmentTask.objects.select_related(
        "treatment__primary_anomaly__area", "responsible"
    ).filter(created_at__date__range=(period.date_from, period.date_to))
    if area_id:
        direct = direct.filter(action_plan__anomaly__area_id=area_id)
        treatment = treatment.filter(treatment__primary_anomaly__area_id=area_id)
    rows = []
    for item in direct:
        rows.append(
            {
                "id": str(item.pk), "source": "Directa", "code": item.code or "Sin codigo", "title": item.title,
                "process": item.action_plan.anomaly.area.name, "responsible": _user_name(item.assigned_to),
                "status_key": item.status, "status": item.get_status_display(), "due_date": item.due_date,
                "completed_at": item.completed_at, "created_at": item.created_at,
                "detail_url": f"/actions?item={item.pk}",
            }
        )
    for item in treatment:
        rows.append(
            {
                "id": str(item.pk), "source": "Tratamiento", "code": item.code or "Sin codigo", "title": item.title,
                "process": item.treatment.primary_anomaly.area.name, "responsible": _user_name(item.responsible),
                "status_key": item.status, "status": item.get_status_display(), "due_date": item.execution_date,
                "completed_at": item.completed_at, "created_at": item.created_at,
                "detail_url": f"/treatments?treatment={item.treatment_id}",
            }
        )
    return sorted(rows, key=lambda row: row["created_at"], reverse=True)


def _actions_dashboard(params, period, area_id) -> dict:
    rows = _action_records(period, area_id)
    previous_rows = _action_records(type("Previous", (), {"date_from": period.previous_from, "date_to": period.previous_to})(), area_id)
    today = timezone.localdate()
    open_statuses = {ActionItemStatus.PENDING, ActionItemStatus.IN_PROGRESS}
    status_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    monthly: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    completed_with_due_count = 0
    on_time = 0
    for row in rows:
        effective = "overdue" if row["status_key"] in open_statuses and row["due_date"] and row["due_date"] < today else row["status_key"]
        row["effective_status"] = "Vencida" if effective == "overdue" else row["status"]
        status_counts[effective] += 1
        source_counts[row["source"]] += 1
        monthly[_month_key(row["created_at"])][row["source"]] += 1
        if row["status_key"] == ActionItemStatus.COMPLETED and row["due_date"] and row["completed_at"]:
            completed_with_due_count += 1
            if _local_date(row["completed_at"]) <= row["due_date"]:
                on_time += 1
        row["created_at"] = row["created_at"].isoformat()
        row["completed_at"] = row["completed_at"].isoformat() if row["completed_at"] else None
        row["due_date"] = row["due_date"].isoformat() if row["due_date"] else None
    upcoming = sum(
        1 for row in rows
        if row["status_key"] in open_statuses and row["due_date"] and today <= date.fromisoformat(row["due_date"]) <= today + timedelta(days=7)
    )
    labels = {"Directa": "Acciones directas", "Tratamiento": "Acciones de tratamiento"}
    status_labels = {"pending": "Pendientes", "in_progress": "En curso", "completed": "Completadas", "cancelled": "Canceladas", "overdue": "Vencidas"}
    total = len(rows)
    payload = _base_payload("actions", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Se integran acciones directas y acciones surgidas de tratamientos sin duplicarlas.",
                "Cumplimiento en termino: completadas hasta su fecha comprometida dividido por completadas con fecha comprometida y finalizacion verificable.",
                "Los datos historicos de acciones de tratamiento sin fecha real de finalizacion no integran el denominador.",
            ],
            "metrics": [
                {"key": "total", "label": "Acciones generadas", "value": total, "percentage": None, "tone": "accent", "comparison": _comparison(total, len(previous_rows))},
                {"key": "completed", "label": "Completadas", "value": status_counts.get("completed", 0), "percentage": _safe_percentage(status_counts.get("completed", 0), total), "tone": "success", "comparison": None},
                {"key": "overdue", "label": "Vencidas", "value": status_counts.get("overdue", 0), "percentage": _safe_percentage(status_counts.get("overdue", 0), total), "tone": "warning", "comparison": None},
                {"key": "on_time", "label": "Cumplimiento en termino", "value": on_time, "percentage": _safe_percentage(on_time, completed_with_due_count), "tone": "success", "hint": f"Base verificable: {completed_with_due_count} · Proximas a vencer: {upcoming}", "comparison": None},
            ],
            "series": _series(period, monthly, labels),
            "breakdown": _breakdown(status_counts, status_labels),
            "rows": _paged_rows(rows, params, lambda item: item),
        }
    )
    return payload


def _effectiveness_records(period, area_id) -> list[dict]:
    treatments = Treatment.objects.select_related(
        "primary_anomaly__area", "effectiveness_responsible"
    ).filter(
        Q(effectiveness_evaluation_date__range=(period.date_from, period.date_to))
        | Q(effectiveness_validated_at__date__range=(period.date_from, period.date_to))
    )
    observations = AnomalyImmediateAction.objects.select_related(
        "anomaly__area", "responsible"
    ).filter(
        Q(effectiveness_due_at__range=(period.date_from, period.date_to))
        | Q(effectiveness_verified_at__date__range=(period.date_from, period.date_to))
    )
    if area_id:
        treatments = treatments.filter(primary_anomaly__area_id=area_id)
        observations = observations.filter(anomaly__area_id=area_id)
    rows = []
    for item in treatments:
        rows.append(
            {
                "id": str(item.pk), "source": "Tratamiento", "code": item.code,
                "process": item.primary_anomaly.area.name, "responsible": _user_name(item.effectiveness_responsible),
                "due_date": item.effectiveness_evaluation_date, "verified_at": item.effectiveness_validated_at,
                "result_key": item.effectiveness_validation_result or "pending",
                "result": item.get_effectiveness_validation_result_display() if item.effectiveness_validation_result else "Pendiente",
                "detail_url": f"/treatments?treatment={item.pk}",
            }
        )
    for item in observations:
        result_key = "pending" if item.effectiveness_is_effective is None else "effective" if item.effectiveness_is_effective else "not_effective"
        rows.append(
            {
                "id": str(item.pk), "source": "Observacion", "code": item.anomaly.code,
                "process": item.anomaly.area.name, "responsible": _user_name(item.responsible),
                "due_date": item.effectiveness_due_at, "verified_at": item.effectiveness_verified_at,
                "result_key": result_key, "result": {"pending": "Pendiente", "effective": "Eficaz", "not_effective": "No eficaz"}[result_key],
                "detail_url": f"/anomalies/{item.anomaly_id}",
            }
        )
    return rows


def _effectiveness_dashboard(params, period, area_id) -> dict:
    rows = _effectiveness_records(period, area_id)
    previous = _effectiveness_records(type("Previous", (), {"date_from": period.previous_from, "date_to": period.previous_to})(), area_id)
    today = timezone.localdate()
    counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    monthly: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        key = row["result_key"]
        if key == "pending" and row["due_date"] and row["due_date"] < today:
            key = "overdue"
        row["effective_status"] = {"effective": "Eficaz", "not_effective": "No eficaz", "pending": "Pendiente", "overdue": "Vencida"}[key]
        counts[key] += 1
        source_counts[row["source"]] += 1
        if row["verified_at"]:
            monthly[_month_key(row["verified_at"])][row["result_key"]] += 1
        row["due_date"] = row["due_date"].isoformat() if row["due_date"] else None
        row["verified_at"] = row["verified_at"].isoformat() if row["verified_at"] else None
    performed = counts.get("effective", 0) + counts.get("not_effective", 0)
    reopened = _anomaly_base(area_id).filter(
        detected_at__date__range=(period.date_from, period.date_to), reopened_count__gt=0
    ).count()
    labels = {"effective": "Eficaces", "not_effective": "No eficaces"}
    status_labels = {"effective": "Eficaces", "not_effective": "No eficaces", "pending": "Pendientes", "overdue": "Vencidas"}
    payload = _base_payload("effectiveness", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Integra verificaciones de tratamientos y observaciones, manteniendo identificado el origen.",
                "Porcentaje de eficacia: verificaciones eficaces dividido por verificaciones realizadas; pendientes y vencidas no integran el denominador.",
                "Los resultados mensuales se ubican por fecha real de verificacion.",
            ],
            "metrics": [
                {"key": "performed", "label": "Verificaciones realizadas", "value": performed, "percentage": None, "tone": "accent", "comparison": _comparison(performed, sum(1 for row in previous if row["result_key"] in {"effective", "not_effective"}))},
                {"key": "effective", "label": "Eficaces", "value": counts.get("effective", 0), "percentage": _safe_percentage(counts.get("effective", 0), performed), "tone": "success", "comparison": None},
                {"key": "pending", "label": "Pendientes", "value": counts.get("pending", 0), "percentage": None, "tone": "default", "comparison": None},
                {"key": "overdue", "label": "Vencidas", "value": counts.get("overdue", 0), "percentage": None, "tone": "warning", "hint": f"Anomalias reabiertas del periodo: {reopened}", "comparison": None},
            ],
            "series": _series(period, monthly, labels),
            "breakdown": _breakdown(counts, status_labels),
            "rows": _paged_rows(sorted(rows, key=lambda row: row["verified_at"] or row["due_date"] or "", reverse=True), params, lambda item: item),
        }
    )
    return payload


def _affected_orders_dashboard(params, period, area_id) -> dict:
    queryset = AffectedOrder.objects.select_related("order_type", "anomaly__area").filter(
        anomaly__detected_at__date__range=(period.date_from, period.date_to)
    )
    previous_queryset = AffectedOrder.objects.filter(
        anomaly__detected_at__date__range=(period.previous_from, period.previous_to)
    )
    if area_id:
        queryset = queryset.filter(anomaly__area_id=area_id)
        previous_queryset = previous_queryset.filter(anomaly__area_id=area_id)
    items = list(queryset.order_by("-anomaly__detected_at", "order_type__code", "number"))
    previous_items = list(previous_queryset.only("order_type_id", "number"))
    unique_orders = {(item.order_type_id, item.number.strip().upper()) for item in items}
    previous_unique_orders = {(item.order_type_id, item.number.strip().upper()) for item in previous_items}
    counts: dict[str, int] = defaultdict(int)
    labels: dict[str, str] = {}
    monthly: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows = []
    for item in items:
        key = str(item.order_type_id)
        label = f"{item.order_type.code} - {item.order_type.name}"
        counts[key] += item.quantity
        labels[key] = label
        monthly[_month_key(item.anomaly.detected_at)][key] += item.quantity
        rows.append(
            {
                "id": str(item.pk), "type": item.order_type.code, "number": item.number,
                "quantity": item.quantity, "anomaly": item.anomaly.code, "process": item.anomaly.area.name,
                "detected_at": item.anomaly.detected_at.isoformat(), "detail_url": f"/anomalies/{item.anomaly_id}",
            }
        )
    total_quantity = sum(item.quantity for item in items)
    payload = _base_payload("affected-orders", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Orden unica corresponde a la combinacion tipo y numero; un mismo numero en tipos distintos representa ordenes diferentes.",
                "Registros de afectacion cuenta cada vinculacion entre una anomalia y una orden.",
                "La cantidad total suma las piezas o productos declarados en cada registro de afectacion.",
            ],
            "metrics": [
                {"key": "unique", "label": "Ordenes diferentes", "value": len(unique_orders), "percentage": None, "tone": "accent", "comparison": _comparison(len(unique_orders), len(previous_unique_orders))},
                {"key": "records", "label": "Registros de afectacion", "value": len(items), "percentage": None, "tone": "default", "comparison": _comparison(len(items), previous_queryset.count())},
                {"key": "quantity", "label": "Piezas / productos", "value": total_quantity, "percentage": None, "tone": "warning", "comparison": None},
                {"key": "anomalies", "label": "Anomalias involucradas", "value": len({item.anomaly_id for item in items}), "percentage": None, "tone": "default", "comparison": None},
            ],
            "series": _series(period, monthly, labels),
            "breakdown": _breakdown(counts, labels),
            "rows": _paged_rows(rows, params, lambda item: item),
        }
    )
    return payload


def _learned_lessons_dashboard(params, period, area_id) -> dict:
    treatments = Treatment.objects.select_related(
        "primary_anomaly__area", "responsible", "learned_lesson", "learned_lesson__saved_by"
    ).filter(
        effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
        effectiveness_validated_at__date__range=(period.date_from, period.date_to),
    )
    previous = Treatment.objects.filter(
        effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
        effectiveness_validated_at__date__range=(period.previous_from, period.previous_to),
    )
    if area_id:
        treatments = treatments.filter(primary_anomaly__area_id=area_id)
        previous = previous.filter(primary_anomaly__area_id=area_id)
    items = list(treatments.order_by("-effectiveness_validated_at", "code"))
    counts = {"with_learning": 0, "without_learning": 0, "pending": 0, "procedure_modified": 0}
    monthly: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows = []
    for treatment in items:
        try:
            lesson: TreatmentLearnedLesson | None = treatment.learned_lesson
        except TreatmentLearnedLesson.DoesNotExist:
            lesson = None
        if lesson is None or lesson.has_learning is None:
            state = "pending"
        elif lesson.has_learning:
            state = "with_learning"
        else:
            state = "without_learning"
        counts[state] += 1
        if lesson and lesson.procedure_modified:
            counts["procedure_modified"] += 1
        month = _month_key(treatment.effectiveness_validated_at)
        monthly[month]["effective"] += 1
        if state == "with_learning":
            monthly[month]["with_learning"] += 1
        rows.append(
            {
                "id": str(treatment.pk), "treatment": treatment.code, "anomaly": treatment.primary_anomaly.code,
                "process": treatment.primary_anomaly.area.name,
                "learning": {"with_learning": "Con leccion", "without_learning": "Sin aprendizaje", "pending": "Pendiente de registrar"}[state],
                "procedure_modified": bool(lesson and lesson.procedure_modified),
                "saved_at": lesson.saved_at.isoformat() if lesson and lesson.saved_at else None,
                "validated_at": treatment.effectiveness_validated_at.isoformat(),
                "detail_url": f"/treatments?treatment={treatment.pk}",
            }
        )
    effective = len(items)
    lessons_registered = counts["with_learning"] + counts["without_learning"]
    labels = {"effective": "Tratamientos eficaces", "with_learning": "Con leccion"}
    breakdown_counts = {key: counts[key] for key in ("with_learning", "without_learning", "pending")}
    breakdown_labels = {"with_learning": "Con leccion", "without_learning": "Sin aprendizaje", "pending": "Pendiente de registrar"}
    payload = _base_payload("learned-lessons", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Cobertura de aprendizaje: tratamientos eficaces con leccion dividido por tratamientos eficaces.",
                "Modificacion documental: lecciones con procedimiento modificado dividido por lecciones registradas.",
                "Los tratamientos eficaces sin registro se muestran como pendientes y no se confunden con una decision de sin aprendizaje.",
            ],
            "metrics": [
                {"key": "effective", "label": "Tratamientos eficaces", "value": effective, "percentage": None, "tone": "accent", "comparison": _comparison(effective, previous.count())},
                {"key": "coverage", "label": "Con leccion aprendida", "value": counts["with_learning"], "percentage": _safe_percentage(counts["with_learning"], effective), "tone": "success", "comparison": None},
                {"key": "pending", "label": "Aprendizaje pendiente", "value": counts["pending"], "percentage": _safe_percentage(counts["pending"], effective), "tone": "warning", "comparison": None},
                {"key": "modified", "label": "Procedimiento modificado", "value": counts["procedure_modified"], "percentage": _safe_percentage(counts["procedure_modified"], lessons_registered), "tone": "default", "comparison": None},
            ],
            "series": _series(period, monthly, labels),
            "breakdown": _breakdown(breakdown_counts, breakdown_labels),
            "rows": _paged_rows(rows, params, lambda item: item),
        }
    )
    return payload


def build_phase_three_dashboard(key: str, params) -> dict | None:
    if key not in PHASE_THREE_KEYS:
        return None
    period = _parse_period(params)
    area_id = _parse_area_id(params)
    builders = {
        "finding-classification": _classification_dashboard,
        "repetition-pareto": _repetition_dashboard,
        "actions": _actions_dashboard,
        "effectiveness": _effectiveness_dashboard,
        "affected-orders": _affected_orders_dashboard,
        "learned-lessons": _learned_lessons_dashboard,
    }
    return builders[key](params, period, area_id)
