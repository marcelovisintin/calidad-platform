"""Run with Django shell. Dry-run rolls back all DB changes; two shared PNG fixtures."""
import json
import os
import random
import struct
import zlib
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count
from django.test import override_settings
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.services.access_policy import can_review_findings, is_management_user
from apps.anomalies.models import Anomaly, AnomalyAttachment
from apps.anomalies.services import anomaly_service as a
from apps.actions.models import Treatment, TreatmentTask, TreatmentTaskEvidence
from apps.actions.services import treatment_service as t
from apps.notifications.services import notification_service as n
from apps.catalog.models import Area, AnomalyOrigin, AnomalyType, Priority, OrderType, Severity

APPLY = os.environ.get('QUALITY_TRIAL_APPLY') == '1'
START, END = date(2025, 9, 17), date(2026, 9, 17)
NOW = timezone.now()
PREFIX = 'PRUEBA-600' if APPLY else 'PRUEBA-600-DRY'
FILES = ('quality-trial/evidencia-medicion.png', 'quality-trial/evidencia-inspeccion.png')
RNG = random.Random(20260917)
STATS = Counter()
PLANNED = Counter()
FINISHED = []
SCENARIOS = [
    ('Canto despegado', 'Pegado de cantos', 'Adhesivo insuficiente', 'Caudal de adhesivo sin control al cambio de turno', 'Verificar y ajustar dosificador de adhesivo'),
    ('Perforación descentrada', 'Mecanizado', 'Plantilla desplazada', 'Plantilla sin referencia verificada', 'Recalibrar plantilla y verificar primera pieza'),
    ('Rayas en frente', 'Terminación', 'Contacto durante manipulación', 'Separadores de protección deteriorados', 'Reemplazar separadores y capacitar en manipulación'),
    ('Embalaje deformado', 'Embalaje', 'Presión excesiva', 'Setpoint de cierre sin estándar documentado', 'Definir y verificar setpoint de embalaje'),
    ('Herraje faltante', 'Armado', 'Kit incompleto', 'Preparación de kits sin control visual', 'Implementar verificación visual de kit'),
    ('Diferencia de tonalidad', 'Pintura', 'Variación de mezcla', 'Dosificación sin registro por lote', 'Estandarizar mezcla y registrar lote'),
    ('Medida fuera de tolerancia', 'Corte', 'Desvío de corte', 'Tope sin verificación periódica', 'Ajustar tope y verificar dimensiones'),
    ('Etiqueta incorrecta', 'Despacho', 'Identificación cruzada', 'Etiquetado sin cotejo contra orden', 'Verificar etiqueta y orden antes del despacho'),
    ('Unión desalineada', 'Ensamble', 'Apoyo inestable', 'Dispositivo de montaje con holgura', 'Reparar dispositivo y validar alineación'),
    ('Superficie contaminada', 'Limpieza', 'Polvo residual', 'Frecuencia de limpieza sin criterio por turno', 'Actualizar rutina de limpieza y verificar superficie'),
]
pick = RNG.choice


def day(value, offset):
    return value + timedelta(days=offset)


def at(value):
    if not isinstance(value, datetime):
        value = timezone.make_aware(datetime.combine(value, time(20)))
    return patch('django.utils.timezone.now', return_value=min(value, NOW))


def quota(length, fraction):
    return set(RNG.sample(range(length), round(length * fraction)))


def planned_completion(category, due, early=False):
    # Anomalies are shuffled: balance realized samples while dates remain random.
    late = round((PLANNED[category] + 1) * .3) > PLANNED[category + '_late']
    done = day(due, RNG.randint(1, 7)) if late else day(due, -RNG.randint(0, 4) if early else 0)
    if done <= END:
        PLANNED[category] += 1
        PLANNED[category + '_late'] += late
    return done


def evidence(actor, anomaly=None, task=None, action=None):
    candidates = list(FILES)
    if anomaly is not None and action is None:
        used = set(anomaly.attachments.filter(observation_action__isnull=True).values_list('file', flat=True))
        candidates = [name for name in FILES if name not in used]
    name = pick(candidates)
    data = dict(file=name, original_name=Path(name).name, content_type='image/png', note='Evidencia sintética de prueba; no representa una inspección real.', uploaded_by=actor, created_by=actor, updated_by=actor)
    obj = TreatmentTaskEvidence(treatment_task=task, **data) if task else AnomalyAttachment(anomaly=anomaly, observation_action=action, **data)
    obj.full_clean()
    obj.save()


def finish_task(task, done):
    if done > END:
        return False
    with at(done):
        evidence(task.responsible, task=task)
        t.update_treatment_task(treatment_task=task, user=task.responsible, data=dict(status='completed', evidence_note='Ejecución de prueba completada; muestra sintética conforme.'))
    STATS['completed_treatment_actions'] += 1
    STATS['late_completed_treatment_actions'] += done > task.execution_date
    return True


def rework(trt, owner, scenario, validated):
    restarted = day(validated, RNG.randint(1, 3))
    if restarted > END:
        return
    with at(restarted):
        trt.refresh_from_db()
        causes = [t.add_root_cause(treatment=trt, user=owner, description='Reanálisis: ' + pick([scenario[3], 'El control implementado no cubrió el cambio de turno.'])) for _ in range(pick([1, 2]))]
        tasks = []
        for n in range(pick([1, 2, 3])):
            due = day(restarted, RNG.randint(10, 40))
            task = t.add_treatment_task(treatment=trt, user=owner, data=dict(title='Segundo ciclo: ' + scenario[4], description='Corregir recurrencia y ampliar control a todos los turnos.', root_cause_ids=[causes[n % len(causes)]], responsible=pick(USERS), execution_date=due))
            done = planned_completion('treatment_actions', due, early=True)
            tasks.append((task, done))
        verifier = pick(POOLS['mando_medio_activo'])
        due_validation = day(max(done for _, done in tasks), RNG.randint(5, 10))
        t.update_treatment(treatment=trt, user=owner, data=dict(effectiveness_responsible=verifier, effectiveness_evaluation_date=due_validation, observations='Segundo ciclo tras validación no eficaz.'))
    STATS['retreated_treatments'] += 1
    for task, done in sorted(tasks, key=lambda x: x[1]):
        finish_task(task, done)
    validated = planned_completion('treatment_validations', due_validation) if all(done <= END for _, done in tasks) else day(END, 1)
    if validated <= END and all(done <= END for _, done in tasks):
        with at(validated):
            trt.refresh_from_db()
            t.validate_treatment_effectiveness(treatment=trt, user=verifier, result='effective', comment='Segundo ciclo eficaz; muestra ampliada de prueba sin recurrencia.')
        STATS['retreated_effective_treatments'] += 1
        STATS['treatment_validations'] += 1
        STATS['late_treatment_validations'] += validated > due_validation
        FINISHED.append(('treatment', trt, verifier, validated, scenario))


def treatment(trt, owner, scenario, classified, deadline, idx):
    late = idx in LATE_TREATMENTS
    started = day(deadline, RNG.randint(1, 5)) if late else day(deadline, -RNG.randint(0, 3))
    started = max(started, classified)
    invited = pick([u for u in USERS if u.pk != owner.pk])
    with at(classified):
        t.add_treatment_participant(treatment=trt, participant_user=invited, role='convoked', note='Participante de prueba', user=owner)
        t.confirm_treatment_convocation(treatment=trt, user=owner, scheduled_for=timezone.make_aware(datetime.combine(started, time(10))), treatment_location=pick(['Sala de calidad', 'Sector de producción', 'Oficina técnica']))
    if started > END:
        STATS['scheduled_future_treatments'] += 1
        return
    STATS['started_treatments'] += 1
    STATS['late_started_treatments'] += late
    n_causes = 1 if idx in ONE_CAUSE else 2
    n_actions = TASK_COUNTS[idx]
    STATS[f'treatments_with_{n_causes}_causes'] += 1
    STATS[f'treatments_with_{n_actions}_actions'] += 1
    with at(started):
        t.update_treatment(treatment=trt, user=owner, data=dict(method_used=pick(['five_whys', '6m']), observations=f'Análisis de prueba: {scenario[2]}. Revisar estándar y condiciones del proceso.'))
        trt.refresh_from_db()
        causes = [t.add_root_cause(treatment=trt, user=owner, description=scenario[3] if n == 0 else 'Control de primera pieza no documentado al cambio de lote.') for n in range(n_causes)]
        tasks = []
        for n in range(n_actions):
            due = day(started, RNG.randint(10, 40))
            task = t.add_treatment_task(treatment=trt, user=owner, data=dict(title=scenario[4] if n == 0 else pick(['Actualizar instructivo operativo', 'Capacitar al equipo y verificar aplicación', 'Auditar control de primera pieza']), description=f'Acción correctiva para {scenario[0]}; verificar 10 unidades y registrar resultado.', root_cause_ids=[causes[n % n_causes]], responsible=pick(USERS), execution_date=due))
            done = planned_completion('treatment_actions', due, early=True)
            tasks.append((task, done))
        verifier = pick(POOLS['mando_medio_activo'])
        due_validation = day(max(max(task.execution_date, done) for task, done in tasks), RNG.randint(5, 12))
        t.update_treatment(treatment=trt, user=owner, data=dict(effectiveness_responsible=verifier, effectiveness_evaluation_date=due_validation))
    for task, done in sorted(tasks, key=lambda x: x[1]):
        finish_task(task, done)
    validated = planned_completion('treatment_validations', due_validation) if all(done <= END for _, done in tasks) else day(END, 1)
    if validated > END or any(done > END for _, done in tasks):
        return
    ineffective = RNG.random() < .1
    with at(validated):
        trt.refresh_from_db()
        t.validate_treatment_effectiveness(treatment=trt, user=verifier, result='not_effective' if ineffective else 'effective', comment='La muestra registra recurrencia; se requiere nuevo análisis.' if ineffective else 'Muestra de prueba sin recurrencia del desvío.')
    STATS['treatment_validations'] += 1
    STATS['first_treatment_validations'] += 1
    STATS['late_treatment_validations'] += validated > due_validation
    if ineffective:
        STATS['ineffective_validations'] += 1
        rework(trt, owner, scenario, validated)
    else:
        FINISHED.append(('treatment', trt, verifier, validated, scenario))


def observation(anomaly, owner, scenario, classified):
    with at(classified):
        actions = []
        for _ in range(pick([1, 2])):
            due = day(classified, RNG.randint(10, 40))
            due_validation = day(due, RNG.randint(10, 15))
            action = a.create_observation_action(anomaly=anomaly, user=owner, data=dict(detail=scenario[4], estimated_completion_date=due, effectiveness_due_date=due_validation))
            done = planned_completion('observation_actions', due, early=True)
            actions.append((action, done))
    for action, done in sorted(actions, key=lambda x: x[1]):
        if done <= END:
            with at(done):
                evidence(owner, anomaly=anomaly, action=action)
                a.complete_observation_action(action=action, user=owner, completed_at=done)
            STATS['completed_observation_actions'] += 1
            STATS['late_completed_observation_actions'] += done > action.estimated_completion_date
    due_validation = max(action.effectiveness_due_date for action, _ in actions)
    validated = planned_completion('observation_validations', due_validation) if all(done <= END for _, done in actions) else day(END, 1)
    if validated <= END and all(done <= END for _, done in actions):
        with at(validated):
            anomaly.refresh_from_db()
            a.verify_observation_effectiveness(anomaly=anomaly, user=owner, data=dict(effectiveness_is_effective=True, effectiveness_verified_at=timezone.now(), effectiveness_comment='Verificación de prueba sin recurrencia.', closure_comment='Observación resuelta en muestra sintética.'))
        STATS['observation_validations'] += 1
        STATS['late_observation_validations'] += validated > due_validation
        FINISHED.append(('observation', anomaly, owner, validated, scenario))


def lessons():
    eligible = []
    for record in FINISHED:
        if record[0] == 'treatment':
            record[1].refresh_from_db()
            due = n._treatment_learned_lesson_due_date(record[1])
        else:
            due = n._add_business_days(record[3], 5)
        if due <= END:
            eligible.append((record, due))
    RNG.shuffle(eligible)
    if len(eligible) % 2:
        eligible.pop()  # Leave one native lesson obligation pending for equal halves.
    learning_set = quota(len(eligible), .5)
    native = [idx for idx, (record, _) in enumerate(eligible) if idx in learning_set and record[0] == 'treatment']
    modified_set = set(RNG.sample(native, min(len(native), round(len(learning_set) * .2))))
    late_candidates = [idx for idx, (_, due) in enumerate(eligible) if due < END]
    late_set = set(RNG.sample(late_candidates, round(len(eligible) * .3)))
    for idx, (record, due) in enumerate(eligible):
        done = day(due, RNG.randint(1, min(7, (END - due).days))) if idx in late_set else due
        kind, obj, actor, _, scenario = record
        learning, modified = idx in learning_set, idx in modified_set
        data = dict(has_learning=learning, learned_text=f'Aprendizaje: controlar {scenario[1].lower()} en cambios de lote y turno.' if learning else '', no_learning_reason='' if learning else 'El estándar vigente contemplaba el desvío; se restableció su aplicación sin aprendizaje adicional.', procedure_modified=modified, procedure_modification_notes='Actualizar instructivo, comunicar revisión y verificar aplicación.' if modified else '')
        with at(done):
            obj.refresh_from_db()
            if kind == 'treatment':
                t.save_treatment_learned_lesson(treatment=obj, user=actor, data=data)
                if modified:
                    action = t.add_lesson_derived_action(treatment=obj, user=actor, data=dict(title='Actualizar instructivo y capacitar al equipo', description='Aplicar el aprendizaje de prueba al procedimiento.', responsible=pick(USERS), execution_date=day(done, RNG.randint(10, 40))))
                t.send_treatment_lesson_for_publication(treatment=obj, user=actor)
                t.publish_treatment_lesson(treatment=obj, user=pick(PUBLISHERS))
            else:
                a.save_learning(anomaly=obj, user=actor, data=data)
        if modified:
            completed = planned_completion('treatment_actions', action.execution_date, early=True)
            finish_task(action, completed)
        STATS['lessons'] += 1
        STATS['lessons_with_learning'] += learning
        STATS['lessons_without_learning'] += not learning
        STATS['lessons_procedure_modified'] += modified
        STATS['late_lessons'] += done > due


def generate():
    levels = ['usuario_activo'] * 420 + ['mando_medio_activo'] * 150 + ['administrador'] * 30
    kinds = ['NC'] * 180 + ['OBS_TRT'] * 117 + ['OBS'] * 273 + ['PENDING'] * 30
    RNG.shuffle(levels)
    RNG.shuffle(kinds)
    orders_set, evidence_set = quota(600, .2), quota(600, .3)
    trt_index = 0
    for idx in range(600):
        scenario, area = pick(SCENARIOS), pick(AREAS)
        reporter, owner, admin = pick(POOLS[levels[idx]]), pick(MANAGERS), pick(REVIEWERS)
        generated = day(START, RNG.randint(0, (END - START).days))
        if idx == 0:
            generated = START
        elif idx == 1:
            generated = END
        generated_at = min(timezone.make_aware(datetime.combine(generated, time(RNG.randint(6, 18), RNG.randint(0, 59)))), NOW)
        orders = [dict(order_type=pick(CATALOGS[OrderType]), number=f'TEST-{generated.year}-{idx + 1:05d}-{n}', quantity=RNG.randint(1, 80)) for n in range(1, RNG.randint(1, 3) + 1)] if idx in orders_set else []
        with at(generated_at):
            anomaly = a.create_anomaly(user=reporter, data=dict(code=f'{PREFIX}-{generated.year}-{idx + 1:05d}', title=f'{scenario[0]} · muestra {idx + 1}', description=f'[DATOS DE PRUEBA] {scenario[0]} en {area.name}. Producto: {pick(["Vanitory 60", "Vanitory 80", "Gabinete 100", "Espejo 70"])}. Turno {pick(["mañana", "tarde", "noche"])}; lote TEST-{RNG.randint(1000, 9999)}. Contexto: {pick(["control de primera pieza", "inspección durante cambio de lote", "muestreo al finalizar turno", "revisión previa al despacho"])}.', site=area.site, area=area, imputed_area=pick(AREAS), anomaly_type=pick(CATALOGS[AnomalyType]), anomaly_origin=pick(CATALOGS[AnomalyOrigin]), priority=pick(CATALOGS[Priority]), detected_at=generated_at, affected_process=scenario[1], containment_summary=pick(['Separar unidades para inspección', 'Retener lote y verificar muestra', 'Identificar material y avisar al responsable']), affected_orders=orders))
            if idx in evidence_set:
                for _ in range(RNG.randint(1, 2)):
                    evidence(reporter, anomaly=anomaly)
                    STATS['initial_evidence_files'] += 1
        STATS[f'reporter_{levels[idx]}'] += 1
        STATS[f'classification_{kinds[idx]}'] += 1
        STATS['anomalies_with_orders'] += bool(orders)
        STATS['anomalies_with_initial_evidence'] += idx in evidence_set
        if kinds[idx] == 'PENDING':
            continue
        classified = min(day(generated, RNG.randint(0, 2)), END)
        deadline = day(generated, RNG.randint(5, 10))
        with at(min(timezone.make_aware(datetime.combine(classified, time(19))), NOW)):
            anomaly = a.update_anomaly(anomaly=anomaly, user=admin, data=dict(severity=SEVERITIES['NC' if kinds[idx] == 'NC' else 'OBS'], classification_responsible=owner, observation_due_date=deadline, treatment_deadline=deadline, treatment_comment='Inicio requerido según revisión de prueba.'))
            if kinds[idx].startswith('OBS'):
                a.save_observation_load(anomaly=anomaly, user=owner, data=dict(responsible=owner, observation=scenario[2], action_date=deadline, requires_treatment=kinds[idx] == 'OBS_TRT'))
                anomaly.refresh_from_db()
            if kinds[idx] == 'OBS_TRT':
                trt = Treatment.objects.filter(primary_anomaly=anomaly).first()
                if trt is None:
                    t.create_treatment(primary_anomaly=anomaly, user=owner, responsible=owner, data=dict(deadline=deadline, creation_comment='Observación TRT de prueba.'))
                else:
                    t.update_treatment(treatment=trt, user=owner, data=dict(deadline=deadline, creation_comment='Observación TRT de prueba.'))
        if kinds[idx] == 'OBS':
            observation(anomaly, owner, scenario, classified)
        else:
            trt = Treatment.objects.get(primary_anomaly=anomaly)
            treatment(trt, owner, scenario, classified, deadline, trt_index)
            trt_index += 1
        if (idx + 1) % 50 == 0:
            print(f'Generated {idx + 1}/600', flush=True)


def clear_operations():
    models = [m for m in apps.get_models() if m._meta.app_label in {'anomalies', 'actions', 'audit', 'indicators'} or (m._meta.app_label == 'notifications' and m.__name__ != 'NotificationTemplate')]
    tables = {m._meta.db_table for m in models}
    for model in models:
        tables.update(f.remote_field.through._meta.db_table for f in model._meta.local_many_to_many)
    with connection.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE ' + ', '.join(connection.ops.quote_name(table) for table in sorted(tables)) + ' RESTART IDENTITY')


def write_files():
    for idx, name in enumerate(FILES):
        path = Path(settings.MEDIA_ROOT) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        width, height = 320, 160
        rows = b''.join(b'\x00' + b''.join(bytes((30 + idx * 70, 100 + (x // 20 % 2) * 70, 80 + (y // 20 % 2) * 90)) for x in range(width)) for y in range(height))
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def validate():
    anomalies = Anomaly.objects.filter(code__startswith=PREFIX)
    assert anomalies.count() == 600
    if APPLY:
        assert Anomaly.objects.count() == 600
    for key, count in {'reporter_usuario_activo': 420, 'reporter_mando_medio_activo': 150, 'reporter_administrador': 30, 'anomalies_with_orders': 120, 'anomalies_with_initial_evidence': 180, 'classification_NC': 180, 'classification_OBS': 273, 'classification_OBS_TRT': 117, 'classification_PENDING': 30}.items():
        assert STATS[key] == count, (key, STATS[key])
    assert Treatment.objects.filter(primary_anomaly__in=anomalies).count() == 297
    assert anomalies.filter(severity__code='NC').count() == 180
    assert anomalies.filter(severity__code='OBS').count() == 390
    assert anomalies.filter(severity__isnull=True).count() == 30
    assert anomalies.filter(affected_orders__isnull=False).distinct().count() == 120
    assert anomalies.filter(attachments__observation_action__isnull=True, attachments__isnull=False).distinct().count() == 180
    assert list(User.objects.values_list('pk', 'password', 'access_level', 'is_active').order_by('pk')) == ORIGINAL_USERS
    for total, late in [('completed_treatment_actions', 'late_completed_treatment_actions'), ('completed_observation_actions', 'late_completed_observation_actions'), ('treatment_validations', 'late_treatment_validations'), ('observation_validations', 'late_observation_validations'), ('lessons', 'late_lessons')]:
        assert STATS[late] == round(STATS[total] * .3), (total, STATS[total], late, STATS[late])
    assert STATS['lessons_with_learning'] == STATS['lessons_without_learning']
    assert STATS['lessons_procedure_modified'] == round(STATS['lessons_with_learning'] * .2)
    for anomaly in anomalies.select_related('area', 'site', 'line'):
        anomaly.full_clean()
        assert START <= timezone.localtime(anomaly.created_at).date() <= END
        assert not anomaly.closed_at or anomaly.closed_at <= NOW
        assert not anomaly.closed_at or anomaly.closed_at >= anomaly.created_at
    for task in TreatmentTask.objects.filter(treatment__primary_anomaly__in=anomalies).select_related('responsible'):
        task.full_clean()
        assert task.responsible.is_active
        assert not task.completed_at or task.completed_at <= NOW
        assert not task.completed_at or task.completed_at >= task.created_at
        assert task.derived_from_lesson_id or task.root_causes.exists()
        assert 10 <= (task.execution_date - timezone.localtime(task.created_at).date()).days <= 40
    for trt in Treatment.objects.filter(primary_anomaly__in=anomalies).select_related('primary_anomaly', 'responsible', 'effectiveness_responsible'):
        trt.full_clean()
        assert trt.responsible.is_active and trt.responsible.access_level in {'mando_medio_activo', 'administrador', 'desarrollador'}
        assert 5 <= (trt.deadline - timezone.localtime(trt.primary_anomaly.created_at).date()).days <= 10
        if trt.effectiveness_validation_result == 'effective':
            assert trt.tasks.filter(derived_from_lesson__isnull=True).exclude(status='completed').count() == 0
            assert trt.effectiveness_validated_by_id == trt.effectiveness_responsible_id
        lesson = getattr(trt, 'learned_lesson', None)
        if lesson and lesson.procedure_modified:
            assert lesson.has_learning and lesson.derived_actions.exists()
    return dict(total_anomalies=600, applied=APPLY, seed=20260917, date_from=str(START), date_to=str(END), distribution=dict(STATS), statuses=list(anomalies.values('current_status').annotate(total=Count('pk'))), evidence_files=list(FILES), validation='Passed; user passwords and roles preserved; native workflow services enforced; shared evidence records validated.', assumptions={'remaining_5_percent': 'Pending classification', 'ineffective_rate': 'Approximately 10% of completed first TRT validations', 'overdue': 'Historical completion after deadline; future events stay pending', 'lesson_deadline': 'TRT: native five-business-day policy. Observations: same simulated interval, with no native lesson obligation.', 'procedure_change': '20% of learning lessons, each with native TRT-derived action'})


assert END <= timezone.localdate()
USERS = list(User.objects.filter(is_active=True).order_by('username'))
POOLS = {level: [u for u in USERS if u.access_level == level] for level in ('usuario_activo', 'mando_medio_activo', 'administrador')}
assert all(POOLS.values()), 'Active users required in all three role groups'
MANAGERS = [u for u in USERS if is_management_user(u)]
ADMINS = POOLS['administrador']
REVIEWERS = [u for u in USERS if can_review_findings(u)]
PUBLISHERS = [u for u in USERS if u.is_superuser or u.access_level == 'administrador']
AREAS = list(Area.objects.filter(is_active=True, site__is_active=True).select_related('site').order_by('code'))
CATALOGS = {model: list(model.objects.filter(is_active=True).order_by('code')) for model in (AnomalyOrigin, AnomalyType, Priority, OrderType)}
SEVERITIES = {s.code: s for s in Severity.objects.filter(is_active=True)}
assert AREAS and all(CATALOGS.values()) and {'NC', 'OBS'}.issubset(SEVERITIES)
ORIGINAL_USERS = list(User.objects.values_list('pk', 'password', 'access_level', 'is_active').order_by('pk'))
LATE_TREATMENTS, ONE_CAUSE = quota(297, .2), quota(297, .6)
TASK_COUNTS = [1] * 89 + [2] * 89 + [3] * 119
RNG.shuffle(TASK_COUNTS)
with override_settings(EMAIL_NOTIFICATIONS_ENABLED=False), transaction.atomic():
    if APPLY:
        clear_operations()
        write_files()
    generate()
    lessons()
    REPORT = validate()
    if not APPLY:
        transaction.set_rollback(True)
Path('/tmp/quality-trial-report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(REPORT, ensure_ascii=False, indent=2), flush=True)
