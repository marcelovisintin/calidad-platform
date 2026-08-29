from __future__ import annotations

import csv
import hashlib
import io
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.audit.services import record_audit_event
from apps.indicators.models import IndicatorReport, IndicatorReportStatus
from apps.indicators.services import build_indicator_dashboard
from apps.notifications.models import (
    DeliveryStatus,
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationRecipient,
    NotificationStatus,
    RecipientTaskStatus,
)


REPORT_COLUMNS = {
    "anomalies-treated": [("code", "Codigo"), ("title", "Titulo"), ("process", "Proceso"), ("classification", "Clasificacion"), ("status", "Estado"), ("detected_at", "Detectada"), ("closed_at", "Cerrada")],
    "treatments": [("code", "Tratamiento"), ("anomaly", "Anomalia"), ("process", "Proceso"), ("responsible", "Responsable"), ("status", "Estado"), ("created_at", "Creado"), ("completed_at", "Completado")],
    "anomalies-by-process": [("code", "Codigo"), ("process", "Proceso"), ("count", "Cantidad"), ("percentage", "Porcentaje"), ("previous", "Periodo anterior"), ("delta", "Variacion")],
    "finding-classification": [("code", "Codigo"), ("title", "Titulo"), ("process", "Proceso"), ("classification", "Clasificacion"), ("classified_at", "Clasificada"), ("status", "Estado")],
    "repetition-pareto": [("group", "Grupo"), ("count", "Cantidad"), ("percentage", "Porcentaje"), ("cumulative_percentage", "Acumulado"), ("previous", "Periodo anterior"), ("delta", "Variacion"), ("cases", "Casos")],
    "actions": [("code", "Accion"), ("source", "Origen"), ("title", "Descripcion"), ("process", "Proceso"), ("responsible", "Responsable"), ("effective_status", "Estado"), ("due_date", "Comprometida"), ("completed_at", "Finalizada")],
    "effectiveness": [("code", "Codigo"), ("source", "Circuito"), ("process", "Proceso"), ("responsible", "Responsable"), ("effective_status", "Resultado"), ("due_date", "Vencimiento"), ("verified_at", "Verificada")],
    "affected-orders": [("type", "Tipo"), ("number", "Numero"), ("quantity", "Cantidad"), ("anomaly", "Anomalia"), ("process", "Proceso"), ("detected_at", "Detectada")],
    "learned-lessons": [("treatment", "Tratamiento"), ("anomaly", "Anomalia"), ("process", "Proceso"), ("learning", "Aprendizaje"), ("procedure_modified", "Procedimiento modificado"), ("saved_at", "Registrada"), ("validated_at", "Eficacia validada")],
}


def _all_params(params) -> dict:
    values = {key: params.get(key) for key in ("date_from", "date_to", "area", "group_by") if params.get(key)}
    values["_export_all"] = True
    return values


def _dashboard(key: str, params) -> dict:
    payload = build_indicator_dashboard(key, _all_params(params))
    if payload is None:
        raise ValidationError({"indicator": "El indicador seleccionado no existe."})
    return payload


def _display(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Si" if value else "No"
    return str(value)


def _filename(key: str, payload: dict, extension: str) -> str:
    return f"indicador-{key}-{payload['period']['date_from']}-{payload['period']['date_to']}.{extension}"


def build_csv_response(key: str, params, *, generated_by) -> HttpResponse:
    payload = _dashboard(key, params)
    output = io.StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Indicador", payload["title"]])
    writer.writerow(["Periodo", payload["period"]["date_from"], payload["period"]["date_to"]])
    writer.writerow(["Generado por", generated_by.full_name, "Fecha", timezone.localtime().isoformat()])
    writer.writerow(["Filtros", "; ".join(f"{key}={value}" for key, value in payload["filters"].items() if value)])
    writer.writerow([])
    columns = REPORT_COLUMNS[key]
    writer.writerow([label for _, label in columns])
    for row in payload["rows"]["results"]:
        writer.writerow([_display(row.get(field)) for field, _ in columns])
    filename = _filename(key, payload, "csv")
    response = HttpResponse(output.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _pdf_bytes(payload: dict, generated_by, *, report_id) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=13 * mm,
        rightMargin=13 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=payload["title"],
        author=generated_by.full_name,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#0b4050"), fontSize=19, leading=23))
    styles.add(ParagraphStyle(name="ReportSmall", parent=styles["BodyText"], fontSize=7.5, leading=10, textColor=colors.HexColor("#355f67")))
    styles.add(ParagraphStyle(name="MetricValue", parent=styles["Heading2"], alignment=TA_CENTER, fontSize=15, textColor=colors.HexColor("#0d8b76")))
    story = [
        Paragraph("SCHNEIDER SRL · Sistema de Gestion de Calidad", styles["ReportSmall"]),
        Paragraph(payload["title"], styles["ReportTitle"]),
        Paragraph(payload["description"], styles["BodyText"]),
        Spacer(1, 3 * mm),
        Paragraph(
            f"Informe: {report_id} · Periodo: {payload['period']['date_from']} al {payload['period']['date_to']} · Generado: {timezone.localtime().strftime('%d/%m/%Y %H:%M')} · Usuario: {generated_by.full_name}",
            styles["ReportSmall"],
        ),
        Paragraph(
            "Filtros: " + (" · ".join(f"{key}={value}" for key, value in payload["filters"].items() if value) or "Sin filtros adicionales"),
            styles["ReportSmall"],
        ),
        Spacer(1, 4 * mm),
    ]
    metric_cells = []
    for metric in payload["metrics"]:
        percentage = "" if metric["percentage"] is None else f"<br/><font size='8'>{metric['percentage']:.1f} %</font>"
        metric_cells.append(Paragraph(f"<b>{metric['label']}</b><br/><font size='16'>{metric['value']}</font>{percentage}", styles["MetricValue"]))
    metric_table = Table([metric_cells], colWidths=[(landscape(A4)[0] - 26 * mm) / max(1, len(metric_cells))] * len(metric_cells))
    metric_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcefeb")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#91bdb5")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b4d3ce")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([metric_table, Spacer(1, 5 * mm)])

    if payload["breakdown"]:
        chart_rows = [["Distribucion", "Cantidad", "%", "Representacion"]]
        maximum = max(1, max(item["count"] for item in payload["breakdown"]))
        for item in payload["breakdown"][:12]:
            bar_width = max(1, int((item["count"] / maximum) * 30))
            chart_rows.append([item["label"], item["count"], "Sin base" if item["percentage"] is None else f"{item['percentage']:.1f}", "|" * bar_width])
        chart = Table(chart_rows, colWidths=[65 * mm, 20 * mm, 18 * mm, 135 * mm], repeatRows=1)
        chart.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d8b76")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#56b49d")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c4d8d4")), ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.extend([KeepTogether(chart), Spacer(1, 5 * mm)])

    story.append(Paragraph("Datos de respaldo (primeros 40 registros)", styles["Heading2"]))
    columns = REPORT_COLUMNS[payload["key"]]
    table_rows = [[Paragraph(label, styles["ReportSmall"]) for _, label in columns]]
    for row in payload["rows"]["results"][:40]:
        table_rows.append([Paragraph(_display(row.get(field))[:120], styles["ReportSmall"]) for field, _ in columns])
    if len(table_rows) == 1:
        table_rows.append([Paragraph("Sin datos", styles["ReportSmall"])] + [""] * (len(columns) - 1))
    widths = [(landscape(A4)[0] - 26 * mm) / len(columns)] * len(columns)
    data_table = Table(table_rows, colWidths=widths, repeatRows=1)
    data_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b4050")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b9cfcb")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef7f5")]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    story.extend([data_table, PageBreak(), Paragraph("Criterios y formulas", styles["Heading2"])])
    story.extend(Paragraph(f"• {note}", styles["BodyText"]) for note in payload["formula_notes"])
    story.extend([Spacer(1, 4 * mm), Paragraph(f"Registros filtrados: {payload['rows']['count']} · El CSV contiene el detalle completo.", styles["ReportSmall"])])
    document.build(story)
    return buffer.getvalue()


def eligible_report_recipients():
    return User.objects.filter(is_active=True, email_notifications_enabled=True).exclude(email="").order_by("first_name", "last_name", "username")


@transaction.atomic
def create_and_queue_report(*, key: str, params, recipient_ids: list, actor) -> IndicatorReport:
    eligible_recipients = eligible_report_recipients()
    recipients = list(eligible_recipients.filter(pk__in=recipient_ids))
    if not recipient_ids:
        raise ValidationError({"recipient_ids": "Seleccione al menos un destinatario."})
    if len(recipients) != len(set(str(value) for value in recipient_ids)):
        raise ValidationError({"recipient_ids": "Uno o mas destinatarios no estan habilitados para recibir correo."})
    creator_copy_added = False
    if eligible_recipients.filter(pk=actor.pk).exists() and all(user.pk != actor.pk for user in recipients):
        recipients.append(actor)
        creator_copy_added = True
    payload = _dashboard(key, params)
    report_id = uuid4()
    pdf = _pdf_bytes(payload, actor, report_id=report_id)
    checksum = hashlib.sha256(pdf).hexdigest()
    filename = _filename(key, payload, "pdf")
    now = timezone.now()
    report = IndicatorReport.objects.create(
        id=report_id,
        indicator_key=key,
        period_from=payload["period"]["date_from"],
        period_to=payload["period"]["date_to"],
        filters=payload["filters"],
        status=IndicatorReportStatus.QUEUED,
        row_count=payload["rows"]["count"],
        original_name=filename,
        checksum_sha256=checksum,
        generated_at=now,
        expires_at=now + timedelta(days=30),
        created_by=actor,
        updated_by=actor,
    )
    report.report_file.save(filename, ContentFile(pdf), save=True)
    notification = Notification.objects.create(
        source_type="indicators.indicatorreport",
        source_id=report.pk,
        template_code="indicator_report",
        title=f"Informe de Calidad: {payload['title']}",
        body=f"Se adjunta el informe {payload['title']} correspondiente al periodo {payload['period']['date_from']} al {payload['period']['date_to']}.",
        category=NotificationCategory.INFO,
        status=NotificationStatus.PENDING,
        context_data={"include_action_url_in_email": False, "indicator_report_id": str(report.pk)},
        created_by=actor,
        updated_by=actor,
    )
    NotificationRecipient.objects.bulk_create(
        [
            NotificationRecipient(
                notification=notification,
                user=user,
                channel=NotificationChannel.EMAIL,
                destination=user.email.strip(),
                delivery_status=DeliveryStatus.PENDING,
                task_status=RecipientTaskStatus.NONE,
                created_by=actor,
                updated_by=actor,
            )
            for user in recipients
        ]
    )
    report.notification = notification
    report.save(update_fields=["notification", "updated_at"])
    record_audit_event(
        entity=report,
        action="indicator.report_queued",
        actor=actor,
        after_data={
            "indicator_key": key,
            "recipient_ids": [str(user.pk) for user in recipients],
            "creator_copy_added": creator_copy_added,
            "row_count": report.row_count,
            "checksum_sha256": checksum,
        },
    )
    return report
