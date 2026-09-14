from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.actions.models import Treatment, TreatmentRootCause, TreatmentTask, TreatmentTaskStatus
from apps.anomalies.models import (
    Anomaly,
    AnomalyImmediateAction,
    AnomalyStage,
    AnomalyStatus,
    ObservationAction,
    ObservationResolutionPath,
)
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Site


class ValidationItemsApiTests(APITestCase):
    endpoint = "/api/v1/actions/validation-items/"

    def setUp(self):
        self.admin = self._user("validation_admin", User.AccessLevel.ADMINISTRADOR)
        self.manager = self._user("validation_manager", User.AccessLevel.MANDO_MEDIO_ACTIVO)
        self.other = self._user("validation_other", User.AccessLevel.MANDO_MEDIO_ACTIVO)
        site = Site.objects.create(code="VAL", name="Validation site")
        area = Area.objects.create(site=site, code="VAL", name="Validation area")
        anomaly_type = AnomalyType.objects.create(code="VAL", name="Validation type")
        origin = AnomalyOrigin.objects.create(code="VAL", name="Validation origin")
        priority = Priority.objects.create(code="VAL", name="Validation priority")

        self.manager_anomaly = self._anomaly("20269911-OBS", self.manager, site, area, anomaly_type, origin, priority)
        self.other_anomaly = self._anomaly("20269912-OBS", self.other, site, area, anomaly_type, origin, priority)
        self.manager_treatment = self._treatment("TRT-2099-0011", self.manager, self.manager_anomaly, ready=True)
        self.other_treatment = self._treatment("TRT-2099-0012", self.other, self.other_anomaly, ready=False)

    def _user(self, username, access_level):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="secret123",
            access_level=access_level,
        )

    def _anomaly(self, code, responsible, site, area, anomaly_type, origin, priority):
        anomaly = Anomaly.objects.create(
            code=code,
            title=f"Anomalia {code}",
            description="Validacion de observacion",
            current_status=AnomalyStatus.IN_TREATMENT,
            current_stage=AnomalyStage.EXECUTION_AND_FOLLOW_UP,
            site=site,
            area=area,
            reporter=responsible,
            owner=responsible,
            anomaly_type=anomaly_type,
            anomaly_origin=origin,
            priority=priority,
            detected_at=timezone.now(),
            observation_resolution_path=ObservationResolutionPath.OBSERVATION,
            created_by=self.admin,
            updated_by=self.admin,
        )
        AnomalyImmediateAction.objects.create(
            anomaly=anomaly,
            responsible=responsible,
            action_date=timezone.localdate(),
            observation="Observacion confirmada",
            created_by=self.admin,
            updated_by=self.admin,
        )
        ObservationAction.objects.create(
            anomaly=anomaly,
            sequence=1,
            detail="Accion para validar",
            estimated_completion_date=timezone.localdate(),
            effectiveness_due_date=timezone.localdate() + timedelta(days=1),
            created_by=responsible,
            updated_by=responsible,
        )
        return anomaly

    def _treatment(self, code, responsible, anomaly, *, ready):
        treatment = Treatment.objects.create(
            code=code,
            primary_anomaly=anomaly,
            responsible=responsible,
            scheduled_for=timezone.now() - timedelta(days=1) if ready else None,
            effectiveness_evaluation_date=timezone.localdate(),
            effectiveness_responsible=responsible,
            created_by=self.admin,
            updated_by=self.admin,
        )
        if ready:
            TreatmentRootCause.objects.create(
                treatment=treatment,
                sequence=1,
                description="Causa completa",
                created_by=self.admin,
                updated_by=self.admin,
            )
            TreatmentTask.objects.create(
                treatment=treatment,
                code=f"{code}-A01",
                title="Accion terminada",
                responsible=responsible,
                execution_date=timezone.localdate(),
                status=TreatmentTaskStatus.COMPLETED,
                completed_at=timezone.now(),
                created_by=self.admin,
                updated_by=self.admin,
            )
        return treatment

    def _keys(self, response):
        return {(item["source"], item["id"]) for item in response.data["results"]}

    def test_admin_sees_both_origins_and_all_states(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(
            {item["status"] for item in response.data["results"]},
            {"pending", "blocked"},
        )

    def test_middle_manager_only_sees_own_validations(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self.endpoint)
        self.assertEqual(
            self._keys(response),
            {
                ("treatment", str(self.manager_treatment.pk)),
                ("observation", str(self.manager_anomaly.pk)),
            },
        )

    def test_future_validation_dates_block_both_origins_until_the_due_date(self):
        self.manager_treatment.effectiveness_evaluation_date = timezone.localdate() + timedelta(days=1)
        self.manager_treatment.save(update_fields=["effectiveness_evaluation_date", "updated_at"])
        self.client.force_authenticate(user=self.manager)

        future_response = self.client.get(self.endpoint)
        future_items = {
            item["source"]: item
            for item in future_response.data["results"]
        }
        for source in ("treatment", "observation"):
            self.assertEqual(future_items[source]["status"], "blocked")
            self.assertFalse(future_items[source]["available"])
            self.assertFalse(future_items[source]["can_validate"])
            self.assertTrue(
                any("fecha de validacion" in blocker.lower() for blocker in future_items[source]["blockers"])
            )

        self.manager_treatment.effectiveness_evaluation_date = timezone.localdate()
        self.manager_treatment.save(update_fields=["effectiveness_evaluation_date", "updated_at"])
        self.manager_anomaly.observation_actions.update(effectiveness_due_date=timezone.localdate())

        due_response = self.client.get(self.endpoint)
        due_items = {
            item["source"]: item
            for item in due_response.data["results"]
        }
        for source in ("treatment", "observation"):
            self.assertEqual(due_items[source]["status"], "pending")
            self.assertTrue(due_items[source]["available"])
            self.assertTrue(due_items[source]["can_validate"])

    def test_source_checks_support_each_origin_and_neither(self):
        self.client.force_authenticate(user=self.admin)
        treatments = self.client.get(f"{self.endpoint}?source=treatment")
        observations = self.client.get(f"{self.endpoint}?source=observation")
        neither = self.client.get(f"{self.endpoint}?source=")
        self.assertEqual({item["source"] for item in treatments.data["results"]}, {"treatment"})
        self.assertEqual({item["source"] for item in observations.data["results"]}, {"observation"})
        self.assertEqual(neither.data["count"], 0)

    def test_api_root_advertises_validation_items(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/v1/actions/")
        self.assertEqual(response.data["validation_items"], self.endpoint)
