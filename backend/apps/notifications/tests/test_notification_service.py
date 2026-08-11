from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.anomalies.models import ParticipantRole
from apps.anomalies.services.anomaly_service import add_participant, create_anomaly
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site
from apps.notifications.models import (
    DeliveryStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationRecipient,
    NotificationStatus,
    NotificationTaskType,
    RecipientTaskStatus,
)
from apps.notifications.selectors import notification_summary_for_user
from apps.notifications.services.email_delivery import dispatch_pending_email_notifications
from apps.notifications.services.notification_service import create_internal_notification


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
        )
        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

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

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_anomaly_creation_queues_confirmation_email_for_opted_in_reporter(self):
        self.reporter.email_notifications_enabled = True
        self.reporter.save(update_fields=["email_notifications_enabled", "updated_at"])

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
