from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.actions.models import Treatment, TreatmentParticipantRole, TreatmentRootCause, TreatmentTaskStatus
from apps.actions.services.treatment_service import (
    add_treatment_participant,
    add_treatment_task,
    update_treatment,
    update_treatment_task,
)
from apps.anomalies.models import ParticipantRole
from apps.anomalies.services.anomaly_service import add_participant, create_anomaly, update_anomaly
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site
from apps.notifications.models import (
    DeliveryStatus,
    NotificationCategory,
    NotificationChannel,
    Notification,
    NotificationRecipient,
    NotificationStatus,
    NotificationTaskType,
    RecipientTaskStatus,
)
from apps.notifications.selectors import notification_summary_for_user
from apps.notifications.services.email_delivery import dispatch_pending_email_notifications
from apps.notifications.services.notification_service import create_internal_notification, resolve_notification_task


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.reporter = User.objects.create_user(
            username="reporter",
            email="reporter@example.com",
            password="secret123",
        )
        self.analyst = User.objects.create_user(
            username="analyst",
            email="analyst@example.com",
            password="secret123",
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

    def _create_treatment(self) -> Treatment:
        anomaly = create_anomaly(
            user=self.admin,
            data={
                "site": self.site,
                "area": self.area,
                "reporter": self.reporter,
                "anomaly_type": self.anomaly_type,
                "anomaly_origin": self.anomaly_origin,
                "severity": self.severity,
                "priority": self.priority,
                "title": "Anomalía para tratamiento",
                "description": "Descripción",
                "detected_at": timezone.now(),
            },
            request_id="req-treatment-anomaly",
        )
        return Treatment.objects.create(
            code="TRT-001",
            primary_anomaly=anomaly,
            scheduled_for=timezone.now() + timezone.timedelta(days=1),
            treatment_location="Sala de Calidad",
            created_by=self.admin,
            updated_by=self.admin,
        )

    def _create_unclassified_anomaly(self, *, title: str = "Hallazgo pendiente"):
        return create_anomaly(
            user=self.admin,
            data={
                "site": self.site,
                "area": self.area,
                "reporter": self.reporter,
                "anomaly_type": self.anomaly_type,
                "anomaly_origin": self.anomaly_origin,
                "priority": self.priority,
                "title": title,
                "description": "Descripción del hallazgo.",
                "detected_at": timezone.now(),
            },
            request_id="req-unclassified-anomaly",
        )

    def _prepare_treatment_task(self, *, responsible=None):
        treatment = self._create_treatment()
        responsible = responsible or self.analyst
        add_treatment_participant(
            treatment=treatment,
            participant_user=responsible,
            role=TreatmentParticipantRole.CONVOKED,
            note="Responsable de tarea.",
            user=self.admin,
        )
        root_cause = TreatmentRootCause.objects.create(
            treatment=treatment,
            sequence=1,
            description="Causa raíz de prueba.",
            created_by=self.admin,
            updated_by=self.admin,
        )
        task = add_treatment_task(
            treatment=treatment,
            data={
                "root_cause_ids": [root_cause],
                "title": "Actualizar instructivo",
                "description": "Revisar y publicar el instructivo actualizado.",
                "responsible": responsible,
                "execution_date": timezone.localdate() + timezone.timedelta(days=3),
                "status": TreatmentTaskStatus.PENDING,
                "anomaly_ids": [treatment.primary_anomaly_id],
            },
            user=self.admin,
            request_id="req-treatment-task",
        )
        return treatment, root_cause, task

    def test_anomaly_creation_and_participation_generate_internal_notifications(self):
        anomaly = create_anomaly(
            user=self.admin,
            data={
                "site": self.site,
                "area": self.area,
                "reporter": self.reporter,
                "anomaly_type": self.anomaly_type,
                "anomaly_origin": self.anomaly_origin,
                "severity": self.severity,
                "priority": self.priority,
                "title": "Desviacion de prueba",
                "description": "Descripcion",
                "detected_at": timezone.now(),
            },
            request_id="req-anomaly",
        )

        reporter_notification = NotificationRecipient.objects.get(
            notification__source_type="anomalies.anomaly",
            notification__source_id=anomaly.pk,
            user=self.reporter,
        )
        self.assertEqual(reporter_notification.notification.category, NotificationCategory.ANOMALY)
        self.assertFalse(reporter_notification.notification.is_task)
        self.assertIn(anomaly.code, reporter_notification.notification.title)
        self.assertEqual(
            reporter_notification.notification.context_data["initial_status"],
            anomaly.current_status,
        )
        self.assertEqual(notification_summary_for_user(self.reporter)["unread"], 1)

        add_participant(
            anomaly=anomaly,
            user=self.admin,
            data={
                "user": self.analyst,
                "role": ParticipantRole.ANALYST,
                "note": "Participacion en analisis.",
            },
            request_id="req-participant",
        )

        analyst_task = NotificationRecipient.objects.get(
            notification__task_type=NotificationTaskType.ANALYSIS_PARTICIPATION,
            user=self.analyst,
        )
        self.assertTrue(analyst_task.notification.is_task)
        self.assertEqual(analyst_task.task_status, RecipientTaskStatus.PENDING)
        summary = notification_summary_for_user(self.analyst)
        self.assertEqual(summary["tasks_total"], 1)
        self.assertEqual(summary["tasks_pending"], 1)

    def test_tasks_endpoint_separates_open_and_completed_tasks(self):
        pending = create_internal_notification(
            recipients=[self.reporter],
            title="Gestión pendiente",
            body="Debe gestionar el hallazgo.",
            source_type="anomalies.anomaly",
            source_id=self._create_unclassified_anomaly().pk,
            actor=self.admin,
            is_task=True,
            task_type=NotificationTaskType.FINDING_MANAGEMENT,
        )
        completed = create_internal_notification(
            recipients=[self.reporter],
            title="Tarea completada",
            body="La tarea ya fue realizada.",
            source_type="anomalies.anomaly",
            source_id=self._create_unclassified_anomaly(title="Hallazgo completado").pk,
            actor=self.admin,
            is_task=True,
            task_type=NotificationTaskType.ACTION_ASSIGNMENT,
        )
        completed_recipient = completed.recipients.get(
            user=self.reporter,
            channel=NotificationChannel.IN_APP,
        )
        resolve_notification_task(
            recipient=completed_recipient,
            user=self.reporter,
            task_status=RecipientTaskStatus.COMPLETED,
        )

        client = APIClient()
        client.force_authenticate(user=self.reporter)
        open_response = client.get("/api/v1/notifications/inbox/tasks/")
        completed_response = client.get("/api/v1/notifications/inbox/tasks/?task_status=completed")

        self.assertEqual(open_response.status_code, 200)
        self.assertEqual(completed_response.status_code, 200)
        self.assertEqual({item["title"] for item in open_response.data["results"]}, {pending.title})
        self.assertEqual({item["title"] for item in completed_response.data["results"]}, {completed.title})

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_anomaly_creation_queues_confirmation_email_for_opted_in_reporter(self):
        self.reporter.email_notifications_enabled = True
        self.reporter.access_level = User.AccessLevel.MANDO_MEDIO_ACTIVO
        self.reporter.save(update_fields=["email_notifications_enabled", "access_level", "updated_at"])

        anomaly = create_anomaly(
            user=self.admin,
            data={
                "site": self.site,
                "area": self.area,
                "reporter": self.reporter,
                "anomaly_type": self.anomaly_type,
                "anomaly_origin": self.anomaly_origin,
                "severity": self.severity,
                "priority": self.priority,
                "title": "Desviación detectada",
                "description": "Descripción",
                "detected_at": timezone.now(),
            },
            request_id="req-anomaly-email",
        )

        recipients = NotificationRecipient.objects.filter(
            notification__source_type="anomalies.anomaly",
            notification__source_id=anomaly.pk,
            user=self.reporter,
        )
        email_recipient = recipients.get(channel=NotificationChannel.EMAIL)
        notification = email_recipient.notification
        self.assertEqual(recipients.count(), 2)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.PENDING)
        self.assertEqual(notification.template_code, "anomaly_created")
        self.assertEqual(notification.status, NotificationStatus.PENDING)
        self.assertIn("registrada correctamente", notification.title)
        self.assertIn(anomaly.title, notification.body)
        self.assertIn(self.area.name, notification.body)
        self.assertEqual(notification.action_url, f"/anomalies/{anomaly.pk}")
        self.assertEqual(notification_summary_for_user(self.reporter)["unread"], 1)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_global_switch_prevents_email_queue_creation(self):
        self.reporter.email_notifications_enabled = True
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])

        notification = create_internal_notification(
            recipients=[self.reporter],
            title="Notificacion de prueba",
            body="Contenido de prueba.",
            source_type="notifications.test",
            source_id=self.reporter.pk,
            email_enabled=True,
        )

        self.assertEqual(notification.status, NotificationStatus.SENT)
        self.assertEqual(notification.recipients.count(), 1)
        self.assertFalse(notification.recipients.filter(channel=NotificationChannel.EMAIL).exists())

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="calidad@example.com",
        APP_PUBLIC_URL="http://calidad.local:8088",
        EMAIL_RETRY_DELAY_MINUTES=0,
        EMAIL_PROCESSING_TIMEOUT_MINUTES=10,
        EMAIL_MAX_RETRIES=3,
    )
    def test_opted_in_user_email_is_queued_and_delivered(self):
        self.reporter.email_notifications_enabled = True
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])
        notification = create_internal_notification(
            recipients=[self.reporter],
            title="Notificacion de prueba",
            body="Contenido de prueba.",
            source_type="notifications.test",
            source_id=self.reporter.pk,
            action_url="/anomalies/test/",
            email_enabled=True,
        )

        email_recipient = notification.recipients.get(channel=NotificationChannel.EMAIL)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.PENDING)
        self.assertEqual(email_recipient.destination, self.reporter.email)
        self.assertEqual(notification_summary_for_user(self.reporter)["total"], 1)

        result = dispatch_pending_email_notifications()

        self.assertEqual(result["delivered"], 1)
        email_recipient.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.DELIVERED)
        self.assertEqual(email_recipient.delivery_attempts, 1)
        self.assertIsNotNone(email_recipient.delivered_at)
        self.assertEqual(notification.status, NotificationStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.reporter.email])
        self.assertIn("http://calidad.local:8088/anomalies/test/", mail.outbox[0].body)

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="calidad@example.com",
        APP_PUBLIC_URL="http://calidad.local:8088",
        EMAIL_RETRY_DELAY_MINUTES=0,
        EMAIL_PROCESSING_TIMEOUT_MINUTES=10,
        EMAIL_MAX_RETRIES=3,
    )
    def test_email_failure_is_recorded_and_can_be_retried(self):
        self.reporter.email_notifications_enabled = True
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])
        notification = create_internal_notification(
            recipients=[self.reporter],
            title="Notificacion con reintento",
            body="Contenido de prueba.",
            source_type="notifications.test",
            source_id=self.reporter.pk,
            email_enabled=True,
        )

        with patch(
            "apps.notifications.services.email_delivery.EmailMultiAlternatives.send",
            side_effect=[RuntimeError("SMTP no disponible"), 1],
        ):
            first_result = dispatch_pending_email_notifications()
            second_result = dispatch_pending_email_notifications()

        email_recipient = notification.recipients.get(channel=NotificationChannel.EMAIL)
        notification.refresh_from_db()
        self.assertEqual(first_result["failed"], 1)
        self.assertEqual(second_result["delivered"], 1)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.DELIVERED)
        self.assertEqual(email_recipient.delivery_attempts, 2)
        self.assertEqual(email_recipient.delivery_error, "")
        self.assertEqual(notification.status, NotificationStatus.SENT)

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_RETRY_DELAY_MINUTES=0,
        EMAIL_PROCESSING_TIMEOUT_MINUTES=10,
        EMAIL_MAX_RETRIES=3,
    )
    def test_opt_out_before_dispatch_skips_queued_email(self):
        self.reporter.email_notifications_enabled = True
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])
        notification = create_internal_notification(
            recipients=[self.reporter],
            title="Notificacion cancelada",
            body="Contenido de prueba.",
            source_type="notifications.test",
            source_id=self.reporter.pk,
            email_enabled=True,
        )
        self.reporter.email_notifications_enabled = False
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])

        result = dispatch_pending_email_notifications()

        email_recipient = notification.recipients.get(channel=NotificationChannel.EMAIL)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.SKIPPED)
        self.assertIn("desactivó", email_recipient.delivery_error)

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        APP_PUBLIC_URL="http://calidad.local:8088",
    )
    def test_treatment_invitation_queues_email_for_opted_in_participant(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        treatment = self._create_treatment()

        participant = add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.FACILITATOR,
            note="Participar del análisis.",
            user=self.admin,
            request_id="req-treatment-participant",
        )

        recipients = NotificationRecipient.objects.filter(
            notification__source_type="actions.treatment",
            notification__source_id=treatment.pk,
            user=self.analyst,
        )
        email_recipient = recipients.get(channel=NotificationChannel.EMAIL)
        notification = email_recipient.notification
        self.assertEqual(recipients.count(), 2)
        self.assertEqual(email_recipient.destination, self.analyst.email)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.PENDING)
        self.assertEqual(notification.template_code, "treatment_participant_invited")
        self.assertEqual(notification.task_type, NotificationTaskType.TREATMENT_PARTICIPATION)
        self.assertTrue(notification.is_task)
        self.assertEqual(notification.action_url, f"/treatments?treatment={treatment.pk}")
        self.assertIn(treatment.code, notification.title)
        self.assertIn(treatment.primary_anomaly.code, notification.body)
        self.assertIn("Facilitador", notification.body)
        self.assertIn(treatment.treatment_location, notification.body)
        self.assertEqual(notification.context_data["participant_id"], str(participant.pk))
        self.assertFalse(notification.context_data["include_action_url_in_email"])
        self.assertEqual(notification_summary_for_user(self.analyst)["tasks_pending"], 1)

        result = dispatch_pending_email_notifications()

        self.assertEqual(result["delivered"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("Abrir en el sistema", mail.outbox[0].body)
        self.assertNotIn(f"/treatments?treatment={treatment.pk}", mail.outbox[0].body)
        self.assertIn("con tu propio usuario", mail.outbox[0].body)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_treatment_participant_update_does_not_duplicate_invitation(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        treatment = self._create_treatment()
        participant = add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.CONVOKED,
            note="Primera convocatoria.",
            user=self.admin,
        )

        updated_participant = add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.OWNER,
            note="Se actualiza el rol.",
            user=self.admin,
        )

        self.assertEqual(updated_participant.pk, participant.pk)
        self.assertEqual(updated_participant.role, TreatmentParticipantRole.OWNER)
        notifications = NotificationRecipient.objects.filter(
            notification__source_type="actions.treatment",
            notification__source_id=treatment.pk,
            notification__template_code="treatment_participant_invited",
            user=self.analyst,
        )
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(notifications.filter(channel=NotificationChannel.EMAIL).count(), 1)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_treatment_invitation_does_not_queue_email_for_opted_out_participant(self):
        treatment = self._create_treatment()

        add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.CONVOKED,
            note="Convocatoria sin correo.",
            user=self.admin,
        )

        recipients = NotificationRecipient.objects.filter(
            notification__source_type="actions.treatment",
            notification__source_id=treatment.pk,
            user=self.analyst,
        )
        self.assertEqual(recipients.count(), 1)
        self.assertTrue(recipients.filter(channel=NotificationChannel.IN_APP).exists())
        self.assertFalse(recipients.filter(channel=NotificationChannel.EMAIL).exists())

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_nonconformity_responsible_receives_finding_management_task_and_email(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        nonconformity = Severity.objects.create(code="NC", name="No Conformidad")
        anomaly = self._create_unclassified_anomaly(title="Desvío dimensional")

        updated = update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={
                "severity": nonconformity,
                "classification_responsible": self.analyst,
            },
            request_id="req-nc-responsible",
        )

        recipients = NotificationRecipient.objects.filter(
            notification__template_code="finding_management_assigned",
            notification__source_id=anomaly.pk,
        )
        email_recipient = recipients.get(channel=NotificationChannel.EMAIL)
        notification = email_recipient.notification
        self.assertEqual(updated.owner, self.analyst)
        self.assertEqual(recipients.count(), 2)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.PENDING)
        self.assertEqual(notification.task_type, NotificationTaskType.FINDING_MANAGEMENT)
        self.assertEqual(notification.action_url, f"/treatments?anomaly={anomaly.pk}")
        self.assertIn("crear y coordinar el tratamiento", notification.body)
        self.assertEqual(notification.context_data["management_path"], "treatment")

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_observation_responsible_is_asked_to_choose_management_path(self):
        observation = Severity.objects.create(code="OBS", name="Observación")
        anomaly = self._create_unclassified_anomaly(title="Orden y limpieza")

        update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={
                "severity": observation,
                "classification_responsible": self.analyst,
            },
        )

        recipients = NotificationRecipient.objects.filter(
            notification__template_code="finding_management_assigned",
            notification__source_id=anomaly.pk,
        )
        notification = recipients.get(channel=NotificationChannel.IN_APP).notification
        self.assertEqual(recipients.count(), 1)
        self.assertFalse(recipients.filter(channel=NotificationChannel.EMAIL).exists())
        self.assertEqual(notification.action_url, f"/anomalies/{anomaly.pk}")
        self.assertIn("observación directa", notification.body)
        self.assertIn("derivarlo a un tratamiento", notification.body)
        self.assertEqual(notification.context_data["management_path"], "observation_or_treatment")

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_improvement_opportunity_responsible_is_directed_to_treatment(self):
        opportunity = Severity.objects.create(code="OPM", name="Oportunidad de mejora")
        anomaly = self._create_unclassified_anomaly(title="Mejora de proceso")

        update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={
                "severity": opportunity,
                "classification_responsible": self.analyst,
            },
        )

        notification = Notification.objects.get(
            template_code="finding_management_assigned",
            source_id=anomaly.pk,
        )
        self.assertEqual(notification.action_url, f"/treatments?anomaly={anomaly.pk}")
        self.assertIn("crear y coordinar el tratamiento", notification.body)
        self.assertEqual(notification.context_data["severity_code"], opportunity.code)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_responsible_change_dismisses_previous_task_and_pending_email(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        self.reporter.email_notifications_enabled = True
        self.reporter.access_level = User.AccessLevel.MANDO_MEDIO_ACTIVO
        self.reporter.save(update_fields=["email_notifications_enabled", "access_level", "updated_at"])
        nonconformity = Severity.objects.create(code="NC", name="No Conformidad")
        anomaly = self._create_unclassified_anomaly()
        update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={"severity": nonconformity, "classification_responsible": self.analyst},
        )
        previous_notification = Notification.objects.get(
            template_code="finding_management_assigned",
            source_id=anomaly.pk,
        )

        update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={"severity": nonconformity, "classification_responsible": self.reporter},
        )

        previous_in_app = previous_notification.recipients.get(channel=NotificationChannel.IN_APP)
        previous_email = previous_notification.recipients.get(channel=NotificationChannel.EMAIL)
        self.assertEqual(previous_in_app.task_status, RecipientTaskStatus.DISMISSED)
        self.assertEqual(previous_email.task_status, RecipientTaskStatus.DISMISSED)
        self.assertEqual(previous_email.delivery_status, DeliveryStatus.SKIPPED)
        self.assertIn("reemplazada", previous_email.delivery_error)
        active_recipient = NotificationRecipient.objects.get(
            notification__template_code="finding_management_assigned",
            notification__source_id=anomaly.pk,
            channel=NotificationChannel.IN_APP,
            task_status=RecipientTaskStatus.PENDING,
        )
        self.assertEqual(active_recipient.user, self.reporter)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_same_finding_assignment_does_not_create_duplicate_notification(self):
        nonconformity = Severity.objects.create(code="NC", name="No Conformidad")
        anomaly = self._create_unclassified_anomaly()
        classification_data = {
            "severity": nonconformity,
            "classification_responsible": self.analyst,
        }

        update_anomaly(anomaly=anomaly, user=self.admin, data=classification_data.copy())
        update_anomaly(anomaly=anomaly, user=self.admin, data=classification_data.copy())

        self.assertEqual(
            Notification.objects.filter(
                template_code="finding_management_assigned",
                source_id=anomaly.pk,
            ).count(),
            1,
        )

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_invalid_reclassification_dismisses_task_without_new_notification(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        nonconformity = Severity.objects.create(code="NC", name="No Conformidad")
        invalid = Severity.objects.create(
            code="INV",
            name="Inválida",
            requires_classification_responsible=False,
            closes_anomaly_as_invalid=True,
        )
        anomaly = self._create_unclassified_anomaly()
        update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={"severity": nonconformity, "classification_responsible": self.analyst},
        )

        update_anomaly(
            anomaly=anomaly,
            user=self.admin,
            data={
                "severity": invalid,
                "classification_reason": "No corresponde gestionar el hallazgo.",
            },
        )

        self.assertEqual(
            Notification.objects.filter(
                template_code="finding_management_assigned",
                source_id=anomaly.pk,
            ).count(),
            1,
        )
        recipients = NotificationRecipient.objects.filter(
            notification__template_code="finding_management_assigned",
            notification__source_id=anomaly.pk,
        )
        self.assertFalse(recipients.filter(task_status=RecipientTaskStatus.PENDING).exists())
        self.assertEqual(
            recipients.get(channel=NotificationChannel.EMAIL).delivery_status,
            DeliveryStatus.SKIPPED,
        )

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        APP_PUBLIC_URL="http://calidad.local:8088",
    )
    def test_treatment_task_assignment_queues_internal_task_and_email_without_link(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])

        treatment, _root_cause, task = self._prepare_treatment_task()

        recipients = NotificationRecipient.objects.filter(
            notification__source_type="actions.treatmenttask",
            notification__source_id=task.pk,
            user=self.analyst,
        )
        email_recipient = recipients.get(channel=NotificationChannel.EMAIL)
        notification = email_recipient.notification
        self.assertEqual(recipients.count(), 2)
        self.assertEqual(notification.template_code, "treatment_task_assigned")
        self.assertEqual(notification.task_type, NotificationTaskType.ACTION_ASSIGNMENT)
        self.assertEqual(notification.action_url, "/actions/mine")
        self.assertEqual(timezone.localtime(notification.due_at).date(), task.execution_date)
        self.assertIn(task.code, notification.title)
        self.assertIn(task.description, notification.body)
        self.assertIn(treatment.primary_anomaly.code, notification.body)
        self.assertEqual(email_recipient.delivery_status, DeliveryStatus.PENDING)

        result = dispatch_pending_email_notifications()

        self.assertEqual(result["delivered"], 2)
        task_email = next(message for message in mail.outbox if message.subject == notification.title)
        self.assertNotIn("Abrir en el sistema", task_email.body)
        self.assertNotIn("/actions/mine", task_email.body)
        self.assertIn("con tu propio usuario", task_email.body)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_treatment_task_assignment_for_opted_out_user_is_internal_only(self):
        _treatment, _root_cause, task = self._prepare_treatment_task()

        recipients = NotificationRecipient.objects.filter(
            notification__source_type="actions.treatmenttask",
            notification__source_id=task.pk,
            user=self.analyst,
        )
        self.assertEqual(recipients.count(), 1)
        self.assertTrue(recipients.filter(channel=NotificationChannel.IN_APP).exists())
        self.assertFalse(recipients.filter(channel=NotificationChannel.EMAIL).exists())

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_treatment_task_edit_without_reassignment_does_not_duplicate_notification(self):
        treatment, root_cause, task = self._prepare_treatment_task()

        update_treatment_task(
            treatment_task=task,
            data={
                "title": "Actualizar instructivo vigente",
                "root_cause_ids": [root_cause],
            },
            user=self.admin,
        )

        self.assertEqual(
            Notification.objects.filter(
                template_code="treatment_task_assigned",
                source_id=task.pk,
            ).count(),
            1,
        )
        self.assertEqual(treatment.tasks.count(), 1)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_treatment_task_reassignment_cancels_previous_and_notifies_new_responsible(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        self.reporter.email_notifications_enabled = True
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])
        treatment, root_cause, task = self._prepare_treatment_task()
        add_treatment_participant(
            treatment=treatment,
            participant_user=self.reporter,
            role=TreatmentParticipantRole.CONVOKED,
            note="Nuevo responsable de tarea.",
            user=self.admin,
        )

        update_treatment_task(
            treatment_task=task,
            data={
                "responsible": self.reporter,
                "root_cause_ids": [root_cause],
            },
            user=self.admin,
            request_id="req-task-reassigned",
        )

        previous_in_app = NotificationRecipient.objects.get(
            notification__source_type="actions.treatmenttask",
            notification__source_id=task.pk,
            user=self.analyst,
            channel=NotificationChannel.IN_APP,
        )
        previous_email = NotificationRecipient.objects.get(
            notification__source_type="actions.treatmenttask",
            notification__source_id=task.pk,
            user=self.analyst,
            channel=NotificationChannel.EMAIL,
        )
        self.assertEqual(previous_in_app.task_status, RecipientTaskStatus.DISMISSED)
        self.assertEqual(previous_email.task_status, RecipientTaskStatus.DISMISSED)
        self.assertEqual(previous_email.delivery_status, DeliveryStatus.SKIPPED)
        current_recipients = NotificationRecipient.objects.filter(
            notification__source_type="actions.treatmenttask",
            notification__source_id=task.pk,
            user=self.reporter,
        )
        self.assertEqual(current_recipients.count(), 2)
        self.assertEqual(
            current_recipients.get(channel=NotificationChannel.IN_APP).task_status,
            RecipientTaskStatus.PENDING,
        )

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_treatment_task_status_updates_internal_assignment_status(self):
        _treatment, root_cause, task = self._prepare_treatment_task()
        recipient = NotificationRecipient.objects.get(
            notification__source_type="actions.treatmenttask",
            notification__source_id=task.pk,
            user=self.analyst,
            channel=NotificationChannel.IN_APP,
        )

        update_treatment_task(
            treatment_task=task,
            data={
                "status": TreatmentTaskStatus.IN_PROGRESS,
                "evidence_note": "Se inicia la ejecución.",
            },
            user=self.analyst,
        )
        recipient.refresh_from_db()
        self.assertEqual(recipient.task_status, RecipientTaskStatus.IN_PROGRESS)

        update_treatment_task(
            treatment_task=task,
            data={
                "status": TreatmentTaskStatus.COMPLETED,
                "evidence_note": "Tarea finalizada.",
            },
            user=self.analyst,
        )
        recipient.refresh_from_db()
        self.assertEqual(recipient.task_status, RecipientTaskStatus.COMPLETED)
        self.assertIsNotNone(recipient.resolved_at)

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        APP_PUBLIC_URL="http://calidad.local:8088",
    )
    def test_treatment_effectiveness_assignment_queues_task_and_email_without_link(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        treatment = self._create_treatment()
        add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.CONVOKED,
            note="Responsable de eficacia.",
            user=self.admin,
        )
        due_date = timezone.localdate() + timezone.timedelta(days=10)

        treatment = update_treatment(
            treatment=treatment,
            data={
                "effectiveness_evaluation_date": due_date,
                "effectiveness_responsible": self.analyst,
            },
            user=self.admin,
            request_id="req-effectiveness-assignment",
        )

        recipients = NotificationRecipient.objects.filter(
            notification__template_code="treatment_effectiveness_assigned",
            notification__source_id=treatment.pk,
            user=self.analyst,
        )
        email_recipient = recipients.get(channel=NotificationChannel.EMAIL)
        notification = email_recipient.notification
        self.assertEqual(recipients.count(), 2)
        self.assertEqual(notification.task_type, NotificationTaskType.VERIFICATION_PARTICIPATION)
        self.assertEqual(timezone.localtime(notification.due_at).date(), due_date)
        self.assertIn(treatment.code, notification.title)
        self.assertIn(due_date.strftime("%d/%m/%Y"), notification.body)

        dispatch_pending_email_notifications()

        message = next(item for item in mail.outbox if item.subject == notification.title)
        self.assertNotIn("Abrir en el sistema", message.body)
        self.assertNotIn("/treatments", message.body)
        self.assertIn("con tu propio usuario", message.body)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_same_treatment_effectiveness_assignment_is_not_duplicated(self):
        treatment = self._create_treatment()
        add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.CONVOKED,
            note="Responsable de eficacia.",
            user=self.admin,
        )
        due_date = timezone.localdate() + timezone.timedelta(days=10)
        payload = {
            "effectiveness_evaluation_date": due_date,
            "effectiveness_responsible": self.analyst,
        }

        treatment = update_treatment(treatment=treatment, data=payload, user=self.admin)
        update_treatment(treatment=treatment, data=payload, user=self.admin)

        self.assertEqual(
            Notification.objects.filter(
                template_code="treatment_effectiveness_assigned",
                source_id=treatment.pk,
            ).count(),
            1,
        )

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_effectiveness_date_change_replaces_previous_assignment(self):
        self.analyst.email_notifications_enabled = True
        self.analyst.save(update_fields=["email_notifications_enabled", "updated_at"])
        treatment = self._create_treatment()
        add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.CONVOKED,
            note="Responsable de eficacia.",
            user=self.admin,
        )
        first_date = timezone.localdate() + timezone.timedelta(days=7)
        second_date = first_date + timezone.timedelta(days=2)

        treatment = update_treatment(
            treatment=treatment,
            data={
                "effectiveness_evaluation_date": first_date,
                "effectiveness_responsible": self.analyst,
            },
            user=self.admin,
        )
        update_treatment(
            treatment=treatment,
            data={
                "effectiveness_evaluation_date": second_date,
                "effectiveness_responsible": self.analyst,
            },
            user=self.admin,
        )

        recipients = NotificationRecipient.objects.filter(
            notification__template_code="treatment_effectiveness_assigned",
            notification__source_id=treatment.pk,
            user=self.analyst,
        )
        previous_in_app = recipients.get(
            notification__context_data__due_date=first_date.isoformat(),
            channel=NotificationChannel.IN_APP,
        )
        previous_email = recipients.get(
            notification__context_data__due_date=first_date.isoformat(),
            channel=NotificationChannel.EMAIL,
        )
        current_in_app = recipients.get(
            notification__context_data__due_date=second_date.isoformat(),
            channel=NotificationChannel.IN_APP,
        )
        self.assertEqual(previous_in_app.task_status, RecipientTaskStatus.DISMISSED)
        self.assertEqual(previous_email.delivery_status, DeliveryStatus.SKIPPED)
        self.assertEqual(current_in_app.task_status, RecipientTaskStatus.PENDING)

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_opted_out_effectiveness_responsible_receives_internal_task_only(self):
        treatment = self._create_treatment()
        add_treatment_participant(
            treatment=treatment,
            participant_user=self.analyst,
            role=TreatmentParticipantRole.CONVOKED,
            note="Responsable de eficacia.",
            user=self.admin,
        )

        treatment = update_treatment(
            treatment=treatment,
            data={
                "effectiveness_evaluation_date": timezone.localdate() + timezone.timedelta(days=5),
                "effectiveness_responsible": self.analyst,
            },
            user=self.admin,
        )

        recipients = NotificationRecipient.objects.filter(
            notification__template_code="treatment_effectiveness_assigned",
            notification__source_id=treatment.pk,
            user=self.analyst,
        )
        self.assertEqual(recipients.count(), 1)
        self.assertTrue(recipients.filter(channel=NotificationChannel.IN_APP).exists())
