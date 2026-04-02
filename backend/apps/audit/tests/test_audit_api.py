from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.anomalies.models import Anomaly, AnomalyStage, AnomalyStatus
from apps.audit.services import record_audit_event
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site


class AuditApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.viewer = User.objects.create_user(
            username="quality",
            email="quality@example.com",
            password="secret123",
        )
        self.regular_user = User.objects.create_user(
            username="operario",
            email="operario@example.com",
            password="secret123",
        )
        audit_permission = Permission.objects.get(
            content_type__app_label="audit",
            codename="view_auditevent",
        )
        self.viewer.user_permissions.add(audit_permission)

        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

        now = timezone.now()
        self.anomaly = Anomaly.objects.create(
            code="ANO-S01-2026-000001",
            title="Desviacion de prueba",
            description="Descripcion",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area,
            reporter=self.admin,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity,
            priority=self.priority,
            detected_at=now,
            last_transition_at=now,
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.created_event = record_audit_event(
            entity=self.anomaly,
            action="anomaly.created",
            actor=self.admin,
            after_data={"status": AnomalyStatus.REGISTERED},
            request_id="req-audit-created",
        )
        self.updated_event = record_audit_event(
            entity=self.anomaly,
            action="anomaly.updated",
            actor=self.viewer,
            before_data={"status": AnomalyStatus.REGISTERED},
            after_data={"status": AnomalyStatus.IN_EVALUATION},
        )

    def test_audit_api_lists_filters_and_summarizes_events(self):
        self.client.force_authenticate(user=self.viewer)

        root_response = self.client.get("/api/v1/audit/")
        self.assertEqual(root_response.status_code, status.HTTP_200_OK)
        self.assertEqual(root_response.data["events"], "/api/v1/audit/events/")

        list_response = self.client.get("/api/v1/audit/events/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 2)

        detail_response = self.client.get(f"/api/v1/audit/events/{self.updated_event.pk}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["action"], "anomaly.updated")
        self.assertEqual(detail_response.data["before_data"]["status"], AnomalyStatus.REGISTERED)
        self.assertEqual(detail_response.data["after_data"]["status"], AnomalyStatus.IN_EVALUATION)

        filtered_response = self.client.get(
            "/api/v1/audit/events/",
            {"request_id": "req-audit-created"},
        )
        self.assertEqual(filtered_response.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered_response.data["count"], 1)
        self.assertEqual(filtered_response.data["results"][0]["id"], str(self.created_event.pk))

        summary_response = self.client.get(
            "/api/v1/audit/events/summary/",
            {"entity_id": str(self.anomaly.pk)},
        )
        self.assertEqual(summary_response.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_response.data["total"], 2)
        self.assertEqual(summary_response.data["request_tracked"], 1)
        self.assertEqual(summary_response.data["entity_types"], 1)
        self.assertEqual(summary_response.data["action_types"], 2)
        self.assertIsNotNone(summary_response.data["latest_event_at"])

    def test_user_without_audit_permission_cannot_access_api(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get("/api/v1/audit/events/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
