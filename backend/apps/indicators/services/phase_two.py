from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.actions.models import Treatment, TreatmentEffectivenessValidationResult, TreatmentStatus
from apps.anomalies.models import Anomaly, AnomalyStatus
from apps.indicators.catalog import indicator_definition


MONTH_LABELS = (
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
)
PHASE_TWO_KEYS = {"anomalies-treated", "treatments", "anomalies-by-process"}


@dataclass(frozen=True)
class IndicatorPeriod:
    date_from: date
    date_to: date
    previous_from: date
    previous_to: date


def _parse_date(value: str | None, *, field: str, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field: "Use el formato AAAA-MM-DD."}) from exc


def _parse_period(params) -> IndicatorPeriod:
    today = timezone.localdate()
    date_from = _parse_date(params.get("date_from"), field="date_from", default=date(today.year, 1, 1))
    date_to = _parse_date(params.get("date_to"), field="date_to", default=today)
    if date_from > date_to:
        raise ValidationError({"date_to": "Debe ser posterior o igual a la fecha desde."})
    if (date_to - date_from).days > 1826:
        raise ValidationError({"date_to": "El periodo no puede superar cinco anos."})
    duration = date_to - date_from
    previous_to = date_from - timedelta(days=1)
    previous_from = previous_to - duration
    return IndicatorPeriod(date_from, date_to, previous_from, previous_to)


def _parse_area_id(params) -> UUID | None:
    value = (params.get("area") or "").strip()
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValidationError({"area": "El proceso seleccionado no es valido."}) from exc


def _safe_percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _comparison(current: int, previous: int) -> dict:
    return {
        "current": current,
        "previous": previous,
        "delta": current - previous,
        "delta_percentage": None if previous == 0 else round(((current - previous) / previous) * 100, 1),
    }


def _period_payload(period: IndicatorPeriod) -> dict:
    return {
        "date_from": period.date_from.isoformat(),
        "date_to": period.date_to.isoformat(),
        "previous_from": period.previous_from.isoformat(),
        "previous_to": period.previous_to.isoformat(),
    }


def _month_starts(date_from: date, date_to: date) -> list[date]:
    current = date(date_from.year, date_from.month, 1)
    last = date(date_to.year, date_to.month, 1)
    values = []
    while current <= last:
        values.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return values


def _series_counts(queryset, *, date_field: str, period: IndicatorPeriod) -> dict[date, int]:
    rows = (
        queryset.filter(
            **{
                f"{date_field}__date__gte": period.date_from,
                f"{date_field}__date__lte": period.date_to,
            }
        )
        .annotate(month=TruncMonth(date_field))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    return {item["month"].date(): item["total"] for item in rows}


def _paged_rows(queryset, params, serializer) -> dict:
    if params.get("_export_all") is True:
        results = [serializer(item) for item in queryset]
        return {"count": len(results), "page": 1, "page_size": len(results), "pages": 1, "results": results}
    try:
        page_number = max(1, int(params.get("page") or 1))
        page_size = min(100, max(1, int(params.get("page_size") or 20)))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"page": "Pagina o tamano de pagina invalido."}) from exc
    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)
    return {
        "count": paginator.count,
        "page": page.number,
        "page_size": page_size,
        "pages": paginator.num_pages,
        "results": [serializer(item) for item in page.object_list],
    }


def _base_payload(key: str, period: IndicatorPeriod, *, area_id) -> dict:
    definition = indicator_definition(key)
    return {
        **definition,
        "available": True,
        "period": _period_payload(period),
        "filters": {"area": str(area_id) if area_id else ""},
    }


def _anomaly_base(area_id=None):
    queryset = Anomaly.objects.select_related("area", "severity", "reporter")
    return queryset.filter(area_id=area_id) if area_id else queryset


def _treated_anomaly_q() -> Q:
    return Q(current_status=AnomalyStatus.CLOSED) & (
        Q(severity__isnull=True) | Q(severity__closes_anomaly_as_invalid=False)
    )


def _anomaly_row(anomaly: Anomaly) -> dict:
    is_invalid = bool(anomaly.severity and anomaly.severity.closes_anomaly_as_invalid)
    return {
        "id": str(anomaly.pk),
        "code": anomaly.code,
        "title": anomaly.title,
        "process": anomaly.area.name,
        "status": anomaly.get_current_status_display(),
        "classification": anomaly.severity.name if anomaly.severity else "Sin clasificar",
        "detected_at": anomaly.detected_at.isoformat(),
        "closed_at": anomaly.closed_at.isoformat() if anomaly.closed_at else None,
        "treated": anomaly.current_status == AnomalyStatus.CLOSED and not is_invalid,
        "detail_url": f"/anomalies/{anomaly.pk}",
    }


def _anomalies_treated_dashboard(params, period: IndicatorPeriod, area_id) -> dict:
    base = _anomaly_base(area_id)
    generated = base.filter(detected_at__date__range=(period.date_from, period.date_to))
    previous_generated = base.filter(detected_at__date__range=(period.previous_from, period.previous_to))
    treated = base.filter(_treated_anomaly_q(), closed_at__date__range=(period.date_from, period.date_to))
    previous_treated = base.filter(_treated_anomaly_q(), closed_at__date__range=(period.previous_from, period.previous_to))
    generated_count = generated.count()
    treated_count = treated.count()
    previous_generated_count = previous_generated.count()
    previous_treated_count = previous_treated.count()
    cohort_treated = generated.filter(_treated_anomaly_q()).count()
    invalid = generated.filter(severity__closes_anomaly_as_invalid=True).count()
    cancelled = generated.filter(current_status=AnomalyStatus.CANCELLED).count()
    reopened = generated.filter(current_status=AnomalyStatus.REOPENED).count()
    pending = generated.exclude(
        current_status__in=[AnomalyStatus.CLOSED, AnomalyStatus.CANCELLED, AnomalyStatus.REOPENED]
    ).count()

    generated_series = _series_counts(base, date_field="detected_at", period=period)
    treated_series = _series_counts(base.filter(_treated_anomaly_q()), date_field="closed_at", period=period)
    series = [
        {
            "period": month.isoformat(),
            "label": f"{MONTH_LABELS[month.month - 1]} {month.year}",
            "values": [
                {"key": "generated", "label": "Generadas", "count": generated_series.get(month, 0), "percentage": None},
                {"key": "treated", "label": "Tratadas", "count": treated_series.get(month, 0), "percentage": _safe_percentage(treated_series.get(month, 0), generated_series.get(month, 0))},
            ],
        }
        for month in _month_starts(period.date_from, period.date_to)
    ]
    payload = _base_payload("anomalies-treated", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Movimiento: anomalias tratadas en el periodo dividido por anomalias generadas en el periodo.",
                "Cohorte: anomalias generadas en el periodo que actualmente se encuentran tratadas.",
                "Invalidas y anuladas se informan por separado y no se consideran tratadas.",
            ],
            "metrics": [
                {"key": "generated", "label": "Generadas", "value": generated_count, "percentage": None, "tone": "accent", "comparison": _comparison(generated_count, previous_generated_count)},
                {"key": "treated", "label": "Tratadas en el periodo", "value": treated_count, "percentage": _safe_percentage(treated_count, generated_count), "tone": "success", "comparison": _comparison(treated_count, previous_treated_count)},
                {"key": "cohort", "label": "Cohorte tratada", "value": cohort_treated, "percentage": _safe_percentage(cohort_treated, generated_count), "tone": "success", "comparison": None},
                {"key": "pending", "label": "Pendientes de la cohorte", "value": pending, "percentage": _safe_percentage(pending, generated_count), "tone": "warning", "comparison": None},
            ],
            "series": series,
            "breakdown": [
                {"key": "treated", "label": "Tratadas", "count": cohort_treated, "percentage": _safe_percentage(cohort_treated, generated_count)},
                {"key": "pending", "label": "Pendientes", "count": pending, "percentage": _safe_percentage(pending, generated_count)},
                {"key": "invalid", "label": "Invalidas", "count": invalid, "percentage": _safe_percentage(invalid, generated_count)},
                {"key": "cancelled", "label": "Anuladas", "count": cancelled, "percentage": _safe_percentage(cancelled, generated_count)},
                {"key": "reopened", "label": "Reabiertas", "count": reopened, "percentage": _safe_percentage(reopened, generated_count)},
            ],
            "rows": _paged_rows(generated.order_by("-detected_at", "code"), params, _anomaly_row),
        }
    )
    return payload


def _treatment_base(area_id=None):
    queryset = Treatment.objects.select_related("primary_anomaly", "primary_anomaly__area", "responsible")
    return queryset.filter(primary_anomaly__area_id=area_id) if area_id else queryset


def _treatment_row(treatment: Treatment) -> dict:
    responsible = treatment.responsible.full_name if treatment.responsible else "Sin responsable"
    return {
        "id": str(treatment.pk),
        "code": treatment.code,
        "anomaly": treatment.primary_anomaly.code,
        "process": treatment.primary_anomaly.area.name,
        "responsible": responsible,
        "status": treatment.get_status_display(),
        "created_at": treatment.created_at.isoformat(),
        "completed_at": treatment.effectiveness_validated_at.isoformat() if treatment.status == TreatmentStatus.COMPLETED and treatment.effectiveness_validated_at else None,
        "detail_url": f"/treatments?treatment={treatment.pk}",
    }


def _treatments_dashboard(params, period: IndicatorPeriod, area_id) -> dict:
    base = _treatment_base(area_id)
    created = base.filter(created_at__date__range=(period.date_from, period.date_to))
    previous_created = base.filter(created_at__date__range=(period.previous_from, period.previous_to))
    completed = base.filter(
        status=TreatmentStatus.COMPLETED,
        effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
        effectiveness_validated_at__date__range=(period.date_from, period.date_to),
    )
    previous_completed = base.filter(
        status=TreatmentStatus.COMPLETED,
        effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
        effectiveness_validated_at__date__range=(period.previous_from, period.previous_to),
    )
    created_count = created.count()
    completed_count = completed.count()
    cohort_completed = created.filter(status=TreatmentStatus.COMPLETED).count()
    created_series = _series_counts(base, date_field="created_at", period=period)
    completed_series = _series_counts(
        base.filter(status=TreatmentStatus.COMPLETED, effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE),
        date_field="effectiveness_validated_at",
        period=period,
    )
    status_counts = {status: created.filter(status=status).count() for status in TreatmentStatus.values}
    series = [
        {
            "period": month.isoformat(),
            "label": f"{MONTH_LABELS[month.month - 1]} {month.year}",
            "values": [
                {"key": "created", "label": "Creados", "count": created_series.get(month, 0), "percentage": None},
                {"key": "completed", "label": "Completados", "count": completed_series.get(month, 0), "percentage": _safe_percentage(completed_series.get(month, 0), created_series.get(month, 0))},
            ],
        }
        for month in _month_starts(period.date_from, period.date_to)
    ]
    payload = _base_payload("treatments", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Movimiento: tratamientos completados eficazmente en el periodo dividido por tratamientos creados en el periodo.",
                "Cohorte: tratamientos creados en el periodo que actualmente estan completados.",
                "La fecha de finalizacion corresponde a la validacion eficaz del tratamiento.",
            ],
            "metrics": [
                {"key": "created", "label": "Creados", "value": created_count, "percentage": None, "tone": "accent", "comparison": _comparison(created_count, previous_created.count())},
                {"key": "completed", "label": "Completados en el periodo", "value": completed_count, "percentage": _safe_percentage(completed_count, created_count), "tone": "success", "comparison": _comparison(completed_count, previous_completed.count())},
                {"key": "cohort", "label": "Cohorte completada", "value": cohort_completed, "percentage": _safe_percentage(cohort_completed, created_count), "tone": "success", "comparison": None},
                {"key": "open", "label": "Abiertos de la cohorte", "value": sum(status_counts[value] for value in [TreatmentStatus.PENDING, TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS]), "percentage": _safe_percentage(sum(status_counts[value] for value in [TreatmentStatus.PENDING, TreatmentStatus.SCHEDULED, TreatmentStatus.IN_PROGRESS]), created_count), "tone": "warning", "comparison": None},
            ],
            "series": series,
            "breakdown": [
                {"key": status, "label": label, "count": status_counts[status], "percentage": _safe_percentage(status_counts[status], created_count)}
                for status, label in TreatmentStatus.choices
            ],
            "rows": _paged_rows(created.order_by("-created_at", "code"), params, _treatment_row),
        }
    )
    return payload


def _process_row(item) -> dict:
    return item


def _anomalies_by_process_dashboard(params, period: IndicatorPeriod, area_id) -> dict:
    base = _anomaly_base(area_id)
    generated = base.filter(detected_at__date__range=(period.date_from, period.date_to))
    previous = base.filter(detected_at__date__range=(period.previous_from, period.previous_to))
    total = generated.count()
    previous_total = previous.count()
    grouped = list(
        generated.values("area_id", "area__code", "area__name")
        .annotate(count=Count("id"))
        .order_by("-count", "area__name")
    )
    previous_counts = {
        item["area_id"]: item["count"]
        for item in previous.values("area_id").annotate(count=Count("id"))
    }
    breakdown = [
        {
            "key": str(item["area_id"]),
            "label": f"{item['area__code']} - {item['area__name']}",
            "count": item["count"],
            "percentage": _safe_percentage(item["count"], total),
            "comparison": _comparison(item["count"], previous_counts.get(item["area_id"], 0)),
        }
        for item in grouped
    ]
    monthly_rows = (
        generated.annotate(month=TruncMonth("detected_at"))
        .values("month", "area_id", "area__code", "area__name")
        .annotate(count=Count("id"))
        .order_by("month", "area__name")
    )
    monthly_map: dict[date, list[dict]] = {}
    monthly_totals: dict[date, int] = {}
    for item in monthly_rows:
        month = item["month"].date()
        monthly_totals[month] = monthly_totals.get(month, 0) + item["count"]
    for item in monthly_rows:
        month = item["month"].date()
        monthly_map.setdefault(month, []).append(
            {
                "key": str(item["area_id"]),
                "label": f"{item['area__code']} - {item['area__name']}",
                "count": item["count"],
                "percentage": _safe_percentage(item["count"], monthly_totals[month]),
            }
        )
    series = [
        {
            "period": month.isoformat(),
            "label": f"{MONTH_LABELS[month.month - 1]} {month.year}",
            "values": monthly_map.get(month, []),
        }
        for month in _month_starts(period.date_from, period.date_to)
    ]
    top = breakdown[0] if breakdown else None
    row_items = [
        {
            "id": item["key"],
            "code": item["label"].split(" - ", 1)[0],
            "process": item["label"].split(" - ", 1)[-1],
            "count": item["count"],
            "percentage": item["percentage"],
            "previous": item["comparison"]["previous"],
            "delta": item["comparison"]["delta"],
            "detail_url": f"/anomalies?area={item['key']}",
        }
        for item in breakdown
    ]
    payload = _base_payload("anomalies-by-process", period, area_id=area_id)
    payload.update(
        {
            "formula_notes": [
                "Cada anomalia se contabiliza una vez segun el proceso estructurado registrado en el campo area.",
                "El porcentaje representa la participacion del proceso sobre todas las anomalias del periodo.",
            ],
            "metrics": [
                {"key": "total", "label": "Anomalias del periodo", "value": total, "percentage": None, "tone": "accent", "comparison": _comparison(total, previous_total)},
                {"key": "processes", "label": "Procesos con anomalias", "value": len(grouped), "percentage": None, "tone": "default", "comparison": None},
                {"key": "top", "label": "Mayor incidencia", "value": top["count"] if top else 0, "percentage": top["percentage"] if top else None, "tone": "warning", "hint": top["label"] if top else "Sin datos", "comparison": top["comparison"] if top else None},
            ],
            "series": series,
            "breakdown": breakdown,
            "rows": _paged_rows(row_items, params, _process_row),
        }
    )
    return payload


def build_phase_two_dashboard(key: str, params) -> dict | None:
    if key not in PHASE_TWO_KEYS:
        return None
    period = _parse_period(params)
    area_id = _parse_area_id(params)
    if key == "anomalies-treated":
        return _anomalies_treated_dashboard(params, period, area_id)
    if key == "treatments":
        return _treatments_dashboard(params, period, area_id)
    return _anomalies_by_process_dashboard(params, period, area_id)
