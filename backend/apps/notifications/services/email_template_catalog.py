from __future__ import annotations

import logging
from dataclasses import dataclass
from string import Formatter

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.notifications.models import NotificationChannel, NotificationTemplate


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailTemplateField:
    key: str
    label: str
    example: str


@dataclass(frozen=True)
class EmailTemplateDefinition:
    code: str
    case_number: str
    name: str
    stage: str
    recipient: str
    description: str
    conditions: str
    subject_template: str
    body_template: str
    fields: tuple[EmailTemplateField, ...]


def _field(key: str, label: str, example: str) -> EmailTemplateField:
    return EmailTemplateField(key=key, label=label, example=example)


RECIPIENT = _field("recipient_name", "Nombre del destinatario", "María López")
ANOMALY_CODE = _field("anomaly_code", "Número de anomalía", "20269024")
ANOMALY_TITLE = _field("anomaly_title", "Título de la anomalía", "Desvío dimensional")
TREATMENT_CODE = _field("treatment_code", "Número de tratamiento", "TRT-2026-0001")
ACTION_CODE = _field("action_code", "Código de acción", "ACT-20269024-01")
TASK_CODE = _field("task_code", "Código de acción", "TRT-2026-0001-A01")


EMAIL_TEMPLATE_DEFINITIONS = (
    EmailTemplateDefinition(
        code="anomaly_created",
        case_number="1",
        name="Registro de una anomalía",
        stage="Registro",
        recipient="Registrador de la anomalía",
        description="Confirma que la anomalía fue registrada correctamente.",
        conditions="Incluye enlace al detalle de la anomalía.",
        subject_template="Anomalía {anomaly_code} registrada correctamente",
        body_template=(
            "Hola {recipient_name},\n\n"
            "La anomalía {anomaly_code} fue generada correctamente.\n"
            "Título: {anomaly_title}\n"
            "Sector: {area_name}\n"
            "Fecha y hora: {detected_at}\n"
            "Estado inicial: {initial_status}\n"
            "Responsable actual: {responsible_name}."
        ),
        fields=(
            RECIPIENT,
            ANOMALY_CODE,
            ANOMALY_TITLE,
            _field("area_name", "Sector", "Armado"),
            _field("detected_at", "Fecha y hora", "11/09/2026 09:30"),
            _field("initial_status", "Estado inicial", "Registrada"),
            _field("responsible_name", "Responsable actual", "Juan Pérez"),
        ),
    ),
    EmailTemplateDefinition(
        code="finding_management_configured_quality",
        case_number="2.1",
        name="Tratamiento conformado por Calidad",
        stage="Tratamiento creado",
        recipient="Responsable del tratamiento",
        description="Asigna la gestión de un tratamiento conformado por Calidad.",
        conditions="Se registra como pendiente e incluye enlace al tratamiento.",
        subject_template="Tratamiento {treatment_code} conformado por Calidad",
        body_template=(
            "Hola {recipient_name},\n\nFuiste designado responsable del hallazgo {anomaly_code}.\n"
            "Clasificación: {classification}\nTítulo: {anomaly_title}\nSector: {area_name}\n\n"
            "Calidad conformó el tratamiento con {linked_count} anomalía(s). "
            "Debes convocar a los participantes y realizar su gestión."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE, TREATMENT_CODE,
                _field("classification", "Clasificación", "No Conformidad"),
                _field("area_name", "Sector", "Armado"),
                _field("linked_count", "Cantidad de anomalías", "2")),
    ),
    EmailTemplateDefinition(
        code="finding_management_configured_observation",
        case_number="2.2",
        name="Tratamiento conformado desde Observación TRT",
        stage="Tratamiento creado",
        recipient="Responsable del tratamiento",
        description="Comunica la creación del tratamiento desde una Observación TRT.",
        conditions="Se registra como pendiente e incluye enlace al tratamiento.",
        subject_template="Tratamiento {treatment_code} conformado",
        body_template=(
            "Hola {recipient_name},\n\nFuiste designado responsable del hallazgo {anomaly_code}.\n"
            "Clasificación: {classification}\nTítulo: {anomaly_title}\nSector: {area_name}\n\n"
            "Conformaste el tratamiento desde la Observación TRT con {linked_count} anomalía(s). "
            "Debes convocar a los participantes y realizar su gestión."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE, TREATMENT_CODE,
                _field("classification", "Clasificación", "Observación"),
                _field("area_name", "Sector", "Armado"),
                _field("linked_count", "Cantidad de anomalías", "1")),
    ),
    EmailTemplateDefinition(
        code="finding_management_observation_treatment",
        case_number="2.3",
        name="Observación plausible de tratamiento",
        stage="Revisión de hallazgos",
        recipient="Responsable de la observación",
        description="Solicita crear o coordinar el tratamiento de una Observación TRT.",
        conditions="Se registra como pendiente e incluye enlace.",
        subject_template="Tratamiento requerido para la observación TRT {anomaly_code}",
        body_template=(
            "Hola {recipient_name},\n\nFuiste designado responsable del hallazgo {anomaly_code}.\n"
            "Clasificación: {classification}\nTítulo: {anomaly_title}\nSector: {area_name}\n\n"
            "La observación fue marcada como plausible de tratamiento. Debes crear o coordinar su tratamiento."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE,
                _field("classification", "Clasificación", "Observación TRT"),
                _field("area_name", "Sector", "Armado")),
    ),
    EmailTemplateDefinition(
        code="finding_management_observation_direct",
        case_number="2.4",
        name="Gestión directa de observación",
        stage="Revisión de hallazgos / Gestión de observación",
        recipient="Responsable de la observación",
        description="Solicita registrar acciones y verificar la eficacia de la observación.",
        conditions="Se registra como pendiente e incluye enlace a Observaciones.",
        subject_template="Gestión requerida para la observación {anomaly_code}",
        body_template=(
            "Hola {recipient_name},\n\nFuiste designado responsable del hallazgo {anomaly_code}.\n"
            "Clasificación: {classification}\nTítulo: {anomaly_title}\nSector: {area_name}\n\n"
            "La observación fue confirmada para gestión directa. Debes revisar sus datos generales, "
            "registrar las acciones y completar la verificación de eficacia."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE,
                _field("classification", "Clasificación", "Observación"),
                _field("area_name", "Sector", "Armado")),
    ),
    EmailTemplateDefinition(
        code="finding_management_treatment_required",
        case_number="2.5",
        name="Hallazgo que requiere tratamiento",
        stage="Revisión de hallazgos",
        recipient="Responsable asignado",
        description="Solicita crear y coordinar un tratamiento.",
        conditions="Se registra como pendiente e incluye enlace.",
        subject_template="Tratamiento requerido para la anomalía {anomaly_code}",
        body_template=(
            "Hola {recipient_name},\n\nFuiste designado responsable del hallazgo {anomaly_code}.\n"
            "Clasificación: {classification}\nTítulo: {anomaly_title}\nSector: {area_name}\n\n"
            "Debes crear y coordinar el tratamiento, convocando a los participantes necesarios."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE,
                _field("classification", "Clasificación", "No Conformidad"),
                _field("area_name", "Sector", "Armado")),
    ),
    EmailTemplateDefinition(
        code="treatment_anomaly_associated",
        case_number="3",
        name="Anomalía asociada a tratamiento existente",
        stage="Adopta la etapa actual del tratamiento",
        recipient="Responsable del tratamiento",
        description="Avisa que Calidad incorporó una anomalía al tratamiento.",
        conditions="Incluye enlace al tratamiento.",
        subject_template="Anomalía {anomaly_code} asociada al tratamiento {treatment_code}",
        body_template=(
            "Hola {recipient_name},\n\nCalidad asoció la anomalía Nro. {anomaly_code}\n"
            "Al tratamiento Nro. {treatment_code}."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, TREATMENT_CODE),
    ),
    EmailTemplateDefinition(
        code="treatment_participant_invited",
        case_number="4",
        name="Confirmación de convocatoria",
        stage="Tratamiento creado / Convocatoria",
        recipient="Participante convocado",
        description="Comunica la convocatoria, el rol, la fecha y el lugar.",
        conditions="No incluye enlace en el correo.",
        subject_template="Invitación al tratamiento {treatment_code}",
        body_template=(
            "Hola {recipient_name},\n\nFuiste invitado al tratamiento {treatment_code}.\n"
            "Anomalía: {anomaly_code} - {anomaly_title}\nRol: {participant_role}\n"
            "Fecha programada: {scheduled_at}\nLugar: {location}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para consultar y gestionar la invitación."
        ),
        fields=(RECIPIENT, TREATMENT_CODE, ANOMALY_CODE, ANOMALY_TITLE,
                _field("participant_role", "Rol", "Convocado"),
                _field("scheduled_at", "Fecha programada", "15/09/2026 10:00"),
                _field("location", "Lugar", "Sala de Calidad")),
    ),
    EmailTemplateDefinition(
        code="action_item_assigned",
        case_number="5",
        name="Acción general asignada",
        stage="Plan de acción / Ejecución y seguimiento",
        recipient="Responsable de la acción",
        description="Comunica una nueva acción general.",
        conditions="Se registra como pendiente y no incluye enlace en el correo.",
        subject_template="Acción {action_code} asignada",
        body_template=(
            "Hola {recipient_name},\n\nSe te asignó la acción {action_code}.\nTítulo: {action_title}\n"
            "Descripción: {action_description}\nAnomalía: {anomaly_code}\nFecha compromiso: {due_date}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para consultar y gestionar la acción."
        ),
        fields=(RECIPIENT, ACTION_CODE, ANOMALY_CODE,
                _field("action_title", "Título de la acción", "Verificar calibre"),
                _field("action_description", "Descripción", "Controlar el calibre al inicio del turno"),
                _field("due_date", "Fecha compromiso", "18/09/2026")),
    ),
    EmailTemplateDefinition(
        code="action_item_reassigned",
        case_number="6",
        name="Acción general reasignada",
        stage="Plan de acción / Ejecución y seguimiento",
        recipient="Nuevo responsable",
        description="Comunica la reasignación de una acción general.",
        conditions="Descarta el pendiente anterior y no incluye enlace en el correo.",
        subject_template="Acción {action_code} reasignada",
        body_template=(
            "Hola {recipient_name},\n\nSe te asignó la acción {action_code}.\nTítulo: {action_title}\n"
            "Descripción: {action_description}\nAnomalía: {anomaly_code}\nFecha compromiso: {due_date}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para consultar y gestionar la acción."
        ),
        fields=(RECIPIENT, ACTION_CODE, ANOMALY_CODE,
                _field("action_title", "Título de la acción", "Verificar calibre"),
                _field("action_description", "Descripción", "Controlar el calibre al inicio del turno"),
                _field("due_date", "Fecha compromiso", "18/09/2026")),
    ),
    EmailTemplateDefinition(
        code="treatment_task_assigned",
        case_number="7",
        name="Acción de tratamiento asignada",
        stage="Análisis de causa / Plan de acciones / Ejecución",
        recipient="Responsable de la acción",
        description="Comunica una nueva acción del tratamiento.",
        conditions="No incluye enlace en el correo.",
        subject_template="Acción {task_code} asignada",
        body_template=(
            "Hola {recipient_name},\n\nSe te asignó la acción {task_code} del tratamiento {treatment_code}.\n"
            "Título: {task_title}\nDescripción: {task_description}\nAnomalía(s): {anomaly_codes}\n"
            "Fecha de ejecución: {execution_date}.\n\nIngresá al Sistema de Gestión de Calidad con tu propio usuario "
            "para consultar y gestionar la acción."
        ),
        fields=(RECIPIENT, TASK_CODE, TREATMENT_CODE,
                _field("task_title", "Título de la acción", "Ajustar dispositivo"),
                _field("task_description", "Descripción", "Corregir el tope lateral"),
                _field("anomaly_codes", "Anomalías", "20269024, 20269025"),
                _field("execution_date", "Fecha de ejecución", "20/09/2026")),
    ),
    EmailTemplateDefinition(
        code="treatment_task_reassigned",
        case_number="8",
        name="Acción de tratamiento reasignada",
        stage="Ejecución y seguimiento",
        recipient="Nuevo responsable de la acción",
        description="Comunica la reasignación de una acción del tratamiento.",
        conditions="Descarta el pendiente anterior y no incluye enlace en el correo.",
        subject_template="Acción {task_code} reasignada",
        body_template=(
            "Hola {recipient_name},\n\nSe te asignó la acción {task_code} del tratamiento {treatment_code}.\n"
            "Título: {task_title}\nDescripción: {task_description}\nAnomalía(s): {anomaly_codes}\n"
            "Fecha de ejecución: {execution_date}.\n\nIngresá al Sistema de Gestión de Calidad con tu propio usuario "
            "para consultar y gestionar la acción."
        ),
        fields=(RECIPIENT, TASK_CODE, TREATMENT_CODE,
                _field("task_title", "Título de la acción", "Ajustar dispositivo"),
                _field("task_description", "Descripción", "Corregir el tope lateral"),
                _field("anomaly_codes", "Anomalías", "20269024, 20269025"),
                _field("execution_date", "Fecha de ejecución", "20/09/2026")),
    ),
    EmailTemplateDefinition(
        code="treatment_effectiveness_assigned",
        case_number="9",
        name="Verificación de eficacia de tratamiento",
        stage="Verificación de eficacia",
        recipient="Responsable de eficacia",
        description="Asigna la verificación de eficacia del tratamiento.",
        conditions="Requiere responsable y fecha; no incluye enlace en el correo.",
        subject_template="Verificación de eficacia asignada: {treatment_code}",
        body_template=(
            "Hola {recipient_name},\n\nFuiste designado para verificar la eficacia del tratamiento {treatment_code}.\n"
            "Anomalía(s): {anomaly_codes}\nFecha de evaluación: {due_date}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para realizar la verificación."
        ),
        fields=(RECIPIENT, TREATMENT_CODE,
                _field("anomaly_codes", "Anomalías", "20269024, 20269025"),
                _field("due_date", "Fecha de evaluación", "30/09/2026")),
    ),
    EmailTemplateDefinition(
        code="observation_effectiveness_assigned",
        case_number="10",
        name="Verificación de eficacia de observación",
        stage="Verificación de eficacia",
        recipient="Responsable de la observación",
        description="Asigna la verificación de eficacia de una observación.",
        conditions="Se genera al confirmar las acciones; no incluye enlace.",
        subject_template="Verificación de eficacia asignada: {anomaly_code}",
        body_template=(
            "Hola {recipient_name},\n\nDebes verificar la eficacia de la observación {anomaly_code} - {anomaly_title}.\n"
            "Acción realizada: {actions_taken}\nFecha de verificación: {due_date}.\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para realizar la verificación."
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE,
                _field("actions_taken", "Acción realizada", "Se ajustó el dispositivo"),
                _field("due_date", "Fecha de verificación", "30/09/2026")),
    ),
    EmailTemplateDefinition(
        code="anomaly_closed",
        case_number="11",
        name="Cierre individual de anomalía",
        stage="Cierre",
        recipient="Registrador de la anomalía",
        description="Comunica el cierre individual y su motivo.",
        conditions="Aplica a inválida, observación eficaz o cierre administrativo; no incluye enlace.",
        subject_template="Anomalía {anomaly_code} cerrada",
        body_template=(
            "Hola {recipient_name},\n\nLa anomalía {anomaly_code} - {anomaly_title} fue cerrada.\n"
            "Motivo del cierre: {closure_reason}.\nResumen de lo actuado: {closure_summary}"
        ),
        fields=(RECIPIENT, ANOMALY_CODE, ANOMALY_TITLE,
                _field("closure_reason", "Motivo del cierre", "verificación eficaz de la observación"),
                _field("closure_summary", "Resumen", "La gestión fue finalizada")),
    ),
    EmailTemplateDefinition(
        code="treatment_closed",
        case_number="12",
        name="Tratamiento validado como eficaz",
        stage="Verificación de eficacia → Cierre",
        recipient="Usuarios involucrados en el tratamiento",
        description="Comunica el cierre eficaz del tratamiento.",
        conditions="Incluye responsables, participantes y verificadores; no incluye enlace.",
        subject_template="Tratamiento {treatment_code} cerrado eficazmente",
        body_template=(
            "El tratamiento {treatment_code} fue validado como eficaz y quedó cerrado.\n"
            "Anomalía(s) cerrada(s): {anomaly_codes}.\nResultado de la verificación: {validation_comment}"
        ),
        fields=(TREATMENT_CODE,
                _field("anomaly_codes", "Anomalías cerradas", "20269024, 20269025"),
                _field("validation_comment", "Resultado", "Resultado eficaz confirmado")),
    ),
    EmailTemplateDefinition(
        code="anomalies_closed_by_treatment",
        case_number="13",
        name="Cierre de anomalías por tratamiento eficaz",
        stage="Cierre",
        recipient="Registradores no incluidos entre los involucrados",
        description="Informa al registrador el cierre de sus anomalías.",
        conditions="Agrupa las anomalías por registrador y no incluye enlace.",
        subject_template="Cierre de anomalía por tratamiento eficaz {treatment_code}",
        body_template=(
            "Hola {recipient_name},\n\nLa(s) anomalía(s) {reported_anomalies} fue(ron) cerrada(s) porque el tratamiento "
            "{treatment_code} fue validado como eficaz.\nResumen de lo actuado: {validation_comment}"
        ),
        fields=(RECIPIENT, TREATMENT_CODE,
                _field("reported_anomalies", "Anomalías del registrador", "20269024 - Desvío dimensional"),
                _field("validation_comment", "Resumen", "Resultado eficaz confirmado")),
    ),
    EmailTemplateDefinition(
        code="treatment_not_effective",
        case_number="14",
        name="Tratamiento no eficaz",
        stage="Verificación de eficacia → Ejecución y seguimiento",
        recipient="Usuarios involucrados en el tratamiento",
        description="Comunica que el tratamiento permanece abierto.",
        conditions="Evita repetir el mismo evento y no incluye enlace.",
        subject_template="Tratamiento {treatment_code}: resultado no eficaz",
        body_template=(
            "La verificación de eficacia del tratamiento {treatment_code} resultó no eficaz.\n"
            "Observación: {validation_comment}\nEl tratamiento permanece abierto y requiere revisar las acciones realizadas."
        ),
        fields=(TREATMENT_CODE, _field("validation_comment", "Observación", "Persisten desvíos")),
    ),
    EmailTemplateDefinition(
        code="observation_not_effective",
        case_number="15",
        name="Observación no eficaz",
        stage="Verificación de eficacia → Ejecución y seguimiento",
        recipient="Responsable actual de la anomalía",
        description="Comunica que debe registrarse una nueva acción.",
        conditions="La anomalía permanece abierta y el correo no incluye enlace.",
        subject_template="Observación {anomaly_code}: resultado no eficaz",
        body_template=(
            "La verificación de eficacia de la observación {anomaly_code} resultó no eficaz.\n"
            "Observación: {validation_comment}\nLa anomalía permanece abierta y requiere registrar una nueva acción tomada."
        ),
        fields=(ANOMALY_CODE, _field("validation_comment", "Observación", "Persisten desvíos")),
    ),
    EmailTemplateDefinition(
        code="treatment_learned_lesson_published",
        case_number="16",
        name="Primera publicación de lección aprendida",
        stage="Estandarización y aprendizaje",
        recipient="Usuarios involucrados en el tratamiento",
        description="Comunica la conclusión y los cambios de procedimientos.",
        conditions="Solo se envía en la primera publicación y no incluye enlace.",
        subject_template="Lección aprendida publicada: {treatment_code}",
        body_template=(
            "Se publicó el registro de lecciones aprendidas del tratamiento {treatment_code}.\n"
            "Conclusión: {learning_summary}\nProcedimientos: {procedure_summary}"
        ),
        fields=(TREATMENT_CODE,
                _field("learning_summary", "Conclusión", "Se ajustó el control de inicio"),
                _field("procedure_summary", "Procedimientos", "Se modificó el instructivo")),
    ),
    EmailTemplateDefinition(
        code="daily_due_digest",
        case_number="17",
        name="Resumen diario de pendientes",
        stage="Transversal a todas las etapas",
        recipient="Usuario con pendientes próximos o vencidos",
        description="Agrupa los pendientes del usuario en un único correo diario.",
        conditions="Se genera una vez por día desde la hora configurada; no incluye enlace.",
        subject_template="Resumen de pendientes: {overdue_count} vencido(s) y {upcoming_count} próximo(s)",
        body_template=(
            "Hola {recipient_name},\n\n{pending_details}\n\n"
            "Ingresá al Sistema de Gestión de Calidad con tu propio usuario para revisar tus pendientes."
        ),
        fields=(RECIPIENT,
                _field("overdue_count", "Cantidad vencida", "2"),
                _field("upcoming_count", "Cantidad próxima", "3"),
                _field("pending_details", "Detalle de pendientes", "Pendientes vencidos (2):\n- 10/09/2026: Acción ACT-01")),
    ),
    EmailTemplateDefinition(
        code="indicator_report",
        case_number="18",
        name="Informe PDF de indicador",
        stage="Indicadores / Reportes de gestión",
        recipient="Usuarios seleccionados y generador elegible",
        description="Entrega por correo un informe PDF de indicadores.",
        conditions="Correo sin aviso interno; adjunta PDF y no incluye enlace.",
        subject_template="Informe de Calidad: {report_title}",
        body_template="Se adjunta el informe {report_title} correspondiente al periodo {date_from} al {date_to}.",
        fields=(_field("report_title", "Nombre del indicador", "Anomalías generadas"),
                _field("date_from", "Fecha desde", "01/09/2026"),
                _field("date_to", "Fecha hasta", "30/09/2026")),
    ),
    EmailTemplateDefinition(
        code="smtp_configuration_test",
        case_number="19",
        name="Prueba controlada de configuración SMTP",
        stage="Operación técnica",
        recipient="Dirección indicada manualmente",
        description="Valida la configuración del servidor SMTP.",
        conditions="Requiere ejecución manual con --confirm.",
        subject_template="Prueba de correo - Sistema de Gestión de Calidad",
        body_template=(
            "La configuración de correo del Sistema de Gestión de Calidad funciona correctamente.\n\n"
            "Este mensaje es únicamente una prueba controlada."
        ),
        fields=(),
    ),
)


EMAIL_TEMPLATE_BY_CODE = {definition.code: definition for definition in EMAIL_TEMPLATE_DEFINITIONS}


def _template_fields(template: str) -> set[str]:
    fields = set()
    try:
        parsed = Formatter().parse(template)
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if not field_name or "." in field_name or "[" in field_name or format_spec or conversion:
                raise DjangoValidationError("Las variables no admiten atributos, índices ni formatos especiales.")
            fields.add(field_name)
    except ValueError as exc:
        raise DjangoValidationError("El texto contiene llaves sin cerrar. Use {{ y }} para escribir llaves literales.") from exc
    return fields


def validate_email_template(*, definition: EmailTemplateDefinition, subject_template: str, body_template: str) -> None:
    subject = (subject_template or "").strip()
    body = (body_template or "").strip()
    if not subject:
        raise DjangoValidationError({"subject_template": "El asunto es obligatorio."})
    if "\n" in subject or "\r" in subject:
        raise DjangoValidationError({"subject_template": "El asunto debe escribirse en una sola línea."})
    if len(subject) > 255:
        raise DjangoValidationError({"subject_template": "El asunto no puede superar los 255 caracteres."})
    if not body:
        raise DjangoValidationError({"body_template": "El cuerpo es obligatorio."})

    allowed = {field.key for field in definition.fields}
    for field_name, template in (("subject_template", subject), ("body_template", body)):
        try:
            used = _template_fields(template)
        except DjangoValidationError as exc:
            message = exc.messages[0] if exc.messages else str(exc)
            raise DjangoValidationError({field_name: message}) from exc
        unknown = sorted(used - allowed)
        if unknown:
            raise DjangoValidationError(
                {field_name: f"Variables no permitidas: {', '.join('{' + item + '}' for item in unknown)}."}
            )


def render_email_template(
    *,
    code: str,
    context: dict | None = None,
    fallback_subject: str = "",
    fallback_body: str = "",
) -> tuple[str, str]:
    definition = EMAIL_TEMPLATE_BY_CODE.get(code)
    if definition is None:
        return fallback_subject, fallback_body

    override = NotificationTemplate.objects.filter(
        code=code,
        channel=NotificationChannel.EMAIL,
        is_active=True,
    ).first()
    subject_template = override.subject_template if override else definition.subject_template
    body_template = override.body_template if override else definition.body_template
    values = {field.key: field.example for field in definition.fields}
    values.update({key: "" if value is None else str(value) for key, value in (context or {}).items()})
    try:
        subject = subject_template.format_map(values).strip()
        body = body_template.format_map(values).strip()
    except (KeyError, ValueError):
        logger.exception("Plantilla de correo invalida para %s; se utiliza el contenido original.", code)
        return fallback_subject, fallback_body
    return subject[:255], body


def serialize_email_template_definition(definition: EmailTemplateDefinition, override=None) -> dict:
    subject_template = override.subject_template if override else definition.subject_template
    body_template = override.body_template if override else definition.body_template
    example_context = {field.key: field.example for field in definition.fields}
    preview_subject = subject_template.format_map(example_context).strip()
    preview_body = body_template.format_map(example_context).strip()
    return {
        "code": definition.code,
        "case_number": definition.case_number,
        "name": definition.name,
        "stage": definition.stage,
        "recipient": definition.recipient,
        "description": definition.description,
        "conditions": definition.conditions,
        "allowed_fields": [field.__dict__ for field in definition.fields],
        "default_subject_template": definition.subject_template,
        "default_body_template": definition.body_template,
        "subject_template": subject_template,
        "body_template": body_template,
        "preview_subject": preview_subject,
        "preview_body": preview_body,
        "is_customized": override is not None,
        "row_version": override.row_version if override else None,
        "updated_at": override.updated_at if override else None,
        "updated_by": override.updated_by.full_name if override and override.updated_by else None,
    }
