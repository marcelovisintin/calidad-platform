from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.anomalies.models import ParticipantRole
from apps.anomalies.services.anomaly_service import add_participant, create_anomaly
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site
from apps.notifications.models import NotificationCategory, NotificationRecipient, NotificationTaskType, RecipientTaskStatus
from apps.notifications.selectors import notification_summary_for_user


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
