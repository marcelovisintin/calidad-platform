from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.actions.models import Treatment, TreatmentTask, TreatmentTaskStatus
from apps.anomalies.models import (
    Anomaly,
    AnomalyImmediateAction,
    AnomalyStage,
    AnomalyStatus,
    ObservationAction,
    ObservationActionStatus,
    ObservationResolutionPath,
)
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Site


class ActionWorkItemsApiTests(APITestCase):
    endpoint = "/api/v1/actions/work-items/"

    def setUp(self):
        self.admin = User.objects.create_user(
            username="work_items_admin",
            email="work_items_admin@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
        )
        self.developer = User.objects.create_user(
            username="work_items_developer",
            email="work_items_developer@example.com",
            password="secret123",
            access_level=User.AccessLevel.DESARROLLADOR,
        )
        self.manager = User.objects.create_user(
            username="work_items_manager",
            email="work_items_manager@example.com",
            password="secret123",
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        self.other_manager = User.objects.create_user(
            username="work_items_other_manager",
            email="work_items_other_manager@example.com",
            password="secret123",
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )

        site = Site.objects.create(code="WORK", name="Work items site")
        area = Area.objects.create(site=site, code="WORK", name="Work items area")
        anomaly_type = AnomalyType.objects.create(code="WORK", name="Work items type")
        anomaly_origin = AnomalyOrigin.objects.create(code="WORK", name="Work items origin")
        priority = Priority.objects.create(code="WORK", name="Work items priority")

        self.manager_anomaly = self._create_anomaly(
            code="20269901-OBS",
            responsible=self.manager,
            site=site,
            area=area,
            anomaly_type=anomaly_type,
            anomaly_origin=anomaly_origin,
            priority=priority,
        )
        self.other_anomaly = self._create_anomaly(
            code="20269902-OBS",
            responsible=self.other_manager,
            site=site,
            area=area,
            anomaly_type=anomaly_type,
            anomaly_origin=anomaly_origin,
            priority=priority,
        )

        self.treatment = Treatment.objects.create(
            code="TRT-2099-0001",
            primary_anomaly=self.manager_anomaly,
            responsible=self.manager,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.manager_task = TreatmentTask.objects.create(
            treatment=self.treatment,
            code="TRT-WORK-001",
            title="Accion propia de tratamiento",
            responsible=self.manager,
            execution_date=timezone.localdate() + timedelta(days=1),
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.other_task = TreatmentTask.objects.create(
            treatment=self.treatment,
            code="TRT-WORK-002",
            title="Accion ajena de tratamiento",
            responsible=self.other_manager,
            execution_date=timezone.localdate(),
            status=TreatmentTaskStatus.COMPLETED,
            completed_at=timezone.now(),
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.manager_observation_action = ObservationAction.objects.create(
            anomaly=self.manager_anomaly,
            sequence=1,
            detail="Accion propia de Observacion",
            estimated_completion_date=timezone.localdate(),
            effectiveness_due_date=timezone.localdate() + timedelta(days=2),
            status=ObservationActionStatus.COMPLETED,
            completed_at=timezone.localdate(),
            completed_by=self.manager,
            created_by=self.manager,
            updated_by=self.manager,
        )
        self.other_observation_action = ObservationAction.objects.create(
            anomaly=self.other_anomaly,
            sequence=1,
            detail="Accion ajena de Observacion",
            estimated_completion_date=timezone.localdate() + timedelta(days=1),
            effectiveness_due_date=timezone.localdate() + timedelta(days=3),
            created_by=self.other_manager,
            updated_by=self.other_manager,
        )

    def _create_anomaly(
        self,
        *,
        code,
        responsible,
        site,
        area,
        anomaly_type,
        anomaly_origin,
        priority,
    ):
        anomaly = Anomaly.objects.create(
            code=code,
            title=f"Anomalia {code}",
            description=f"Descripcion {code}",
            current_status=AnomalyStatus.IN_TREATMENT,
            current_stage=AnomalyStage.EXECUTION_AND_FOLLOW_UP,
            site=site,
            area=area,
            reporter=responsible,
            owner=responsible,
            anomaly_type=anomaly_type,
            anomaly_origin=anomaly_origin,
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
            observation=f"Observacion {code}",
            created_by=self.admin,
            updated_by=self.admin,
        )
        return anomaly

    def _result_keys(self, response):
        return {(item["source"], item["id"]) for item in response.data["results"]}

    def test_admin_and_developer_see_all_users_and_all_states(self):
        expected = {
            ("treatment", str(self.manager_task.pk)),
            ("treatment", str(self.other_task.pk)),
            ("observation", str(self.manager_observation_action.pk)),
            ("observation", str(self.other_observation_action.pk)),
        }

        for user in (self.admin, self.developer):
            with self.subTest(access_level=user.access_level):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.endpoint)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 4)
                self.assertEqual(self._result_keys(response), expected)

    def test_active_middle_manager_only_sees_own_actions(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._result_keys(response),
            {
                ("treatment", str(self.manager_task.pk)),
                ("observation", str(self.manager_observation_action.pk)),
            },
        )

    def test_source_checks_can_select_each_origin_or_both(self):
        self.client.force_authenticate(user=self.admin)

        treatment_response = self.client.get(f"{self.endpoint}?source=treatment")
        observation_response = self.client.get(f"{self.endpoint}?source=observation")
        both_response = self.client.get(
            f"{self.endpoint}?source=treatment&source=observation"
        )
        neither_response = self.client.get(f"{self.endpoint}?source=")

        self.assertEqual(
            {item["source"] for item in treatment_response.data["results"]},
            {"treatment"},
        )
        self.assertEqual(
            {item["source"] for item in observation_response.data["results"]},
            {"observation"},
        )
        self.assertEqual(both_response.data["count"], 4)
        self.assertEqual(neither_response.data["count"], 0)

    def test_status_and_responsible_filters_apply_to_both_origins(self):
        self.client.force_authenticate(user=self.admin)

        completed_response = self.client.get(f"{self.endpoint}?status=completed")
        completed_on_response = self.client.get(
            f"{self.endpoint}?completed_on={timezone.localdate().isoformat()}"
        )
        responsible_response = self.client.get(
            f"{self.endpoint}?responsible={self.other_manager.pk}"
        )

        self.assertEqual(completed_response.data["count"], 2)
        self.assertEqual(completed_on_response.data["count"], 2)
        self.assertEqual(
            self._result_keys(responsible_response),
            {
                ("treatment", str(self.other_task.pk)),
                ("observation", str(self.other_observation_action.pk)),
            },
        )

    def test_invalid_source_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f"{self.endpoint}?source=unknown")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source", response.data)

    def test_treatment_action_includes_status_change_evidence_notes(self):
        self.client.force_authenticate(user=self.manager)
        update_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{self.manager_task.pk}/",
            {
                "status": TreatmentTaskStatus.IN_PROGRESS,
                "evidence_note": "Material preparado para ejecutar la accion.",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        second_update_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{self.manager_task.pk}/",
            {
                "status": TreatmentTaskStatus.COMPLETED,
                "evidence_note": "Accion terminada con el material recibido.",
            },
            format="json",
        )
        self.assertEqual(second_update_response.status_code, status.HTTP_200_OK)

        response = self.client.get(f"{self.endpoint}?source=treatment")
        item = next(
            item
            for item in response.data["results"]
            if item["id"] == str(self.manager_task.pk)
        )
        self.assertEqual(len(item["status_evidences"]), 2)
        self.assertEqual(
            item["status_evidences"][0]["note"],
            "Accion terminada con el material recibido.",
        )
        self.assertEqual(
            item["status_evidences"][0]["from_status"],
            TreatmentTaskStatus.IN_PROGRESS,
        )
        self.assertEqual(
            item["status_evidences"][0]["to_status"],
            TreatmentTaskStatus.COMPLETED,
        )
        self.assertEqual(
            item["status_evidences"][0]["changed_by"]["id"],
            str(self.manager.pk),
        )
        self.assertEqual(
            item["status_evidences"][1]["note"],
            "Material preparado para ejecutar la accion.",
        )
        self.assertFalse(item["can_cancel"])

    def test_treatment_action_can_complete_directly_but_cannot_go_back(self):
        self.client.force_authenticate(user=self.manager)
        completed_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{self.manager_task.pk}/",
            {
                "status": TreatmentTaskStatus.COMPLETED,
                "evidence_note": "Accion resuelta directamente.",
            },
            format="json",
        )
        self.assertEqual(completed_response.status_code, status.HTTP_200_OK)

        backwards_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{self.manager_task.pk}/",
            {
                "status": TreatmentTaskStatus.IN_PROGRESS,
                "evidence_note": "Intento de retroceso.",
            },
            format="json",
        )
        self.assertEqual(backwards_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", backwards_response.data)

    def test_treatment_action_can_only_cancel_before_first_change(self):
        self.client.force_authenticate(user=self.manager)
        cancel_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{self.manager_task.pk}/",
            {
                "status": TreatmentTaskStatus.CANCELLED,
                "evidence_note": "Accion cancelada antes de comenzar.",
            },
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)

        started_task = TreatmentTask.objects.create(
            treatment=self.treatment,
            code="TRT-WORK-STARTED",
            title="Accion que ya comenzo",
            responsible=self.manager,
            execution_date=timezone.localdate() + timedelta(days=1),
            created_by=self.admin,
            updated_by=self.admin,
        )
        start_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{started_task.pk}/",
            {
                "status": TreatmentTaskStatus.IN_PROGRESS,
                "evidence_note": "Se inicia la accion.",
            },
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        backwards_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{started_task.pk}/",
            {
                "status": TreatmentTaskStatus.PENDING,
                "evidence_note": "Intento de volver a pendiente.",
            },
            format="json",
        )
        self.assertEqual(backwards_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", backwards_response.data)

        second_cancel_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment.pk}/tasks/{started_task.pk}/",
            {
                "status": TreatmentTaskStatus.CANCELLED,
                "evidence_note": "Intento de cancelar luego de comenzar.",
            },
            format="json",
        )
        self.assertEqual(second_cancel_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", second_cancel_response.data)

    def test_api_root_advertises_unified_work_items(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/v1/actions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["work_items"], self.endpoint)
