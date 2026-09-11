import uuid

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.notifications.models import NotificationChannel, NotificationRecipient, NotificationTemplate
from apps.notifications.services.email_delivery import dispatch_pending_email_notifications
from apps.notifications.services.notification_service import create_internal_notification


@override_settings(
    EMAIL_NOTIFICATIONS_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="calidad@example.com",
)
class EmailTemplateManagementTests(TestCase):
    list_url = "/api/v1/notifications/email-templates/"

    def setUp(self):
        self.admin = User.objects.create_user(
            username="quality-admin",
            email="quality-admin@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
            email_notifications_enabled=True,
        )
        self.regular_user = User.objects.create_user(
            username="operator",
            email="operator@example.com",
            password="secret123",
            email_notifications_enabled=True,
        )
        self.client = APIClient()

    def test_admin_can_list_every_case_from_email_matrix(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 23)
        association = next(item for item in response.data if item["code"] == "treatment_anomaly_associated")
        self.assertEqual(association["case_number"], "3")
        self.assertEqual(association["stage"], "Adopta la etapa actual del tratamiento")
        self.assertTrue(association["recipient"])
        self.assertIn("anomaly_code", {field["key"] for field in association["allowed_fields"]})

    def test_regular_user_cannot_access_email_editor(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_variable_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"{self.list_url}anomaly_created/",
            {
                "subject_template": "Anomalía {unknown_field}",
                "body_template": "Se creó {anomaly_code}",
                "row_version": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("subject_template", response.data)

    def test_stale_editor_cannot_overwrite_a_newer_change(self):
        self.client.force_authenticate(user=self.admin)
        first_response = self.client.patch(
            f"{self.list_url}anomaly_created/",
            {
                "subject_template": "Primera versión {anomaly_code}",
                "body_template": "Primera versión para {recipient_name}",
                "row_version": None,
            },
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)

        stale_response = self.client.patch(
            f"{self.list_url}anomaly_created/",
            {
                "subject_template": "Edición desactualizada {anomaly_code}",
                "body_template": "No debe sobrescribir",
                "row_version": None,
            },
            format="json",
        )

        self.assertEqual(stale_response.status_code, 409)
        template = NotificationTemplate.objects.get(code="anomaly_created")
        self.assertEqual(template.subject_template, "Primera versión {anomaly_code}")

    def test_custom_text_is_snapshotted_only_for_future_email(self):
        self.client.force_authenticate(user=self.admin)
        update_response = self.client.patch(
            f"{self.list_url}anomaly_created/",
            {
                "subject_template": "Aviso personalizado {anomaly_code}",
                "body_template": "Hola {recipient_name}. Caso {anomaly_code}: {anomaly_title}.",
                "row_version": None,
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)

        notification = create_internal_notification(
            recipients=[self.regular_user],
            title="Título de la notificación interna",
            body="Cuerpo de la notificación interna",
            source_type="anomalies.anomaly",
            source_id=uuid.uuid4(),
            actor=self.admin,
            email_enabled=True,
            email_template_code="anomaly_created",
            email_context={
                "recipient_name": "Operador",
                "anomaly_code": "AN-2026-0042",
                "anomaly_title": "Prueba de plantilla",
                "reporter_name": "Calidad",
                "area_name": "Producción",
                "detected_at": "11/09/2026 10:00",
            },
        )

        self.assertEqual(notification.title, "Título de la notificación interna")
        email_recipient = NotificationRecipient.objects.get(
            notification=notification,
            channel=NotificationChannel.EMAIL,
        )
        self.assertEqual(email_recipient.email_subject, "Aviso personalizado AN-2026-0042")
        self.assertIn("Hola Operador", email_recipient.email_body)

        result = dispatch_pending_email_notifications()
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(mail.outbox[0].subject, "Aviso personalizado AN-2026-0042")
        self.assertIn("Caso AN-2026-0042", mail.outbox[0].body)

    def test_admin_can_restore_default_text(self):
        NotificationTemplate.objects.create(
            code="anomaly_created",
            channel=NotificationChannel.EMAIL,
            subject_template="Texto personalizado",
            body_template="Cuerpo personalizado",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(f"{self.list_url}anomaly_created/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_customized"])
        self.assertFalse(NotificationTemplate.objects.filter(code="anomaly_created").exists())
