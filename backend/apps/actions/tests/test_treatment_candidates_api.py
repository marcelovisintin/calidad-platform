from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.actions.models import Treatment, TreatmentAnomaly
from apps.anomalies.models import Anomaly, AnomalyStage, AnomalyStatus
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site


class TreatmentCandidatesApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin_candidates",
            email="admin_candidates@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=self.admin)

        self.reporter_one = User.objects.create_user(
            username="reporter_one",
            email="reporter_one@example.com",
            password="secret123",
        )
        self.reporter_two = User.objects.create_user(
            username="reporter_two",
            email="reporter_two@example.com",
            password="secret123",
        )

        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area_one = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.area_two = Area.objects.create(site=self.site, code="A02", name="Area 2")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

        now = timezone.now()
        self.anomaly_one = self._create_anomaly(
            code="20269001",
            title="Anomalia uno",
            reporter=self.reporter_one,
            area=self.area_one,
            detected_at=now - timedelta(days=3),
        )
        self.anomaly_two = self._create_anomaly(
            code="20269002",
            title="Anomalia dos",
            reporter=self.reporter_two,
            area=self.area_two,
            detected_at=now - timedelta(days=2),
        )
        self.anomaly_three = self._create_anomaly(
            code="20269003",
            title="Anomalia tres",
            reporter=self.reporter_one,
            area=self.area_one,
            detected_at=now - timedelta(days=1),
        )

        self.treatment_one = Treatment.objects.create(
            code="TRT-2026-0001",
            primary_anomaly=self.anomaly_one,
            status="pending",
            created_by=self.admin,
            updated_by=self.admin,
        )
        TreatmentAnomaly.objects.create(
            treatment=self.treatment_one,
            anomaly=self.anomaly_one,
            is_primary=True,
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.treatment_two = Treatment.objects.create(
            code="TRT-2026-0002",
            primary_anomaly=self.anomaly_two,
            status="pending",
            created_by=self.admin,
            updated_by=self.admin,
        )
        TreatmentAnomaly.objects.create(
            treatment=self.treatment_two,
            anomaly=self.anomaly_two,
            is_primary=True,
            created_by=self.admin,
            updated_by=self.admin,
        )

    def _create_anomaly(self, *, code: str, title: str, reporter: User, area: Area, detected_at):
        return Anomaly.objects.create(
            code=code,
            title=title,
            description=f"Descripcion {title}",
            current_status=AnomalyStatus.IN_EVALUATION,
            current_stage=AnomalyStage.CLASSIFICATION,
            site=self.site,
            area=area,
            reporter=reporter,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity,
            priority=self.priority,
            detected_at=detected_at,
            created_by=self.admin,
            updated_by=self.admin,
        )

    def test_candidates_for_selected_treatment_include_anomalies_from_other_treatments(self):
        default_response = self.client.get("/api/v1/actions/treatments/candidates/")
        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        default_ids = {item["id"] for item in default_response.data["results"]}
        self.assertIn(str(self.anomaly_three.pk), default_ids)
        self.assertNotIn(str(self.anomaly_one.pk), default_ids)
        self.assertNotIn(str(self.anomaly_two.pk), default_ids)

        scoped_response = self.client.get(f"/api/v1/actions/treatments/candidates/?treatment={self.treatment_one.pk}")
        self.assertEqual(scoped_response.status_code, status.HTTP_200_OK)
        scoped_ids = {item["id"] for item in scoped_response.data["results"]}
        self.assertIn(str(self.anomaly_two.pk), scoped_ids)
        self.assertIn(str(self.anomaly_three.pk), scoped_ids)
        self.assertNotIn(str(self.anomaly_one.pk), scoped_ids)

    def test_candidates_support_filters_for_anomaly_area_user_and_date(self):
        date_from = (timezone.localdate() - timedelta(days=4)).isoformat()
        date_to = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.get(
            "/api/v1/actions/treatments/candidates/"
            f"?treatment={self.treatment_one.pk}"
            "&anomaly=20269002"
            "&area=A02"
            f"&user={self.reporter_two.pk}"
            f"&date_from={date_from}"
            f"&date_to={date_to}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.anomaly_two.pk))
