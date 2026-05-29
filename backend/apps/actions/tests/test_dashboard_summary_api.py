from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.actions.models import ActionItem, ActionItemStatus, ActionPlan, Treatment, TreatmentParticipant, TreatmentTask, TreatmentTaskStatus
from apps.anomalies.models import Anomaly, AnomalyStatus
from apps.catalog.models import ActionType, AnomalyOrigin, AnomalyType, Area, Priority, Site


class DashboardSummaryApiTests(APITestCase):
    def setUp(self):
        self.site = Site.objects.create(code="S01", name="Planta")
        self.area = Area.objects.create(site=self.site, code="CAL", name="Calidad")
        self.anomaly_type = AnomalyType.objects.create(code="DEF", name="Defecto")
        self.origin = AnomalyOrigin.objects.create(code="ORI", name="Origen")
        self.priority = Priority.objects.create(code="MED", name="Media")
        self.action_type = ActionType.objects.create(code="COR", name="Correctiva")
        self.user = User.objects.create_user(username="operario", email="operario@example.com", password="secret123")
        self.other = User.objects.create_user(username="otro", email="otro@example.com", password="secret123")
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
        )
        self.developer = User.objects.create_user(
            username="dev",
            email="dev@example.com",
            password="secret123",
            access_level=User.AccessLevel.DESARROLLADOR,
        )

        self.own_anomaly = self._anomaly("A-001", self.user, AnomalyStatus.IN_TREATMENT)
        self.other_anomaly = self._anomaly("A-002", self.other, AnomalyStatus.CLOSED)
        self.plan = ActionPlan.objects.create(anomaly=self.own_anomaly, owner=self.user)
        self.other_plan = ActionPlan.objects.create(anomaly=self.other_anomaly, owner=self.other)
        ActionItem.objects.create(
            action_plan=self.plan,
            action_type=self.action_type,
            assigned_to=self.user,
            title="Accion propia",
            status=ActionItemStatus.PENDING,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        ActionItem.objects.create(
            action_plan=self.other_plan,
            action_type=self.action_type,
            assigned_to=self.other,
            title="Accion ajena",
            status=ActionItemStatus.COMPLETED,
        )
        own_treatment = Treatment.objects.create(code="T-001", primary_anomaly=self.own_anomaly, status="pending", created_by=self.user)
        TreatmentParticipant.objects.create(treatment=own_treatment, user=self.user)
        TreatmentTask.objects.create(
            treatment=own_treatment,
            title="Tarea propia",
            responsible=self.user,
            status=TreatmentTaskStatus.IN_PROGRESS,
            execution_date=timezone.localdate() - timedelta(days=1),
        )
        other_treatment = Treatment.objects.create(code="T-002", primary_anomaly=self.other_anomaly, status="completed", created_by=self.other)
        TreatmentTask.objects.create(
            treatment=other_treatment,
            title="Tarea ajena",
            responsible=self.other,
            status=TreatmentTaskStatus.COMPLETED,
        )

    def _anomaly(self, code, reporter, status):
        return Anomaly.objects.create(
            code=code,
            title=code,
            description="Caso",
            current_status=status,
            site=self.site,
            area=self.area,
            reporter=reporter,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=reporter,
        )

    def test_common_user_only_gets_own_historical_summary(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/actions/dashboard-summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scope"], "user")
        cards = {item["key"]: item for item in response.data["cards"]}
        self.assertEqual(cards["anomalies"]["total"], 1)
        self.assertEqual(cards["actions"]["total"], 2)
        self.assertEqual(cards["treatments"]["total"], 1)
        self.assertNotIn("detail_rows", cards["anomalies"])

    def test_admin_gets_general_summary_and_user_detail(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/v1/actions/dashboard-summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scope"], "admin")
        cards = {item["key"]: item for item in response.data["cards"]}
        self.assertEqual(cards["anomalies"]["total"], 2)
        self.assertEqual(cards["actions"]["total"], 4)
        self.assertTrue(cards["anomalies"]["detail_rows"])
        self.assertEqual(len(cards["anomalies"]["detail_rows"]), 4)

    def test_developer_access_gets_general_summary_and_user_detail(self):
        self.client.force_authenticate(self.developer)

        response = self.client.get("/api/v1/actions/dashboard-summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scope"], "admin")
        cards = {item["key"]: item for item in response.data["cards"]}
        self.assertEqual(cards["anomalies"]["total"], 2)
        self.assertEqual(cards["actions"]["total"], 4)
        self.assertEqual(cards["treatments"]["total"], 2)
        self.assertTrue(cards["anomalies"]["detail_rows"])
        self.assertEqual(len(cards["anomalies"]["detail_rows"]), 4)
