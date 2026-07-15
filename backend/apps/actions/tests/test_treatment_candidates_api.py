from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User, UserRoleScope
from apps.actions.models import Treatment, TreatmentAnomaly, TreatmentParticipant, TreatmentRootCause, TreatmentTask
from apps.anomalies.models import (
    Anomaly,
    AnomalyClassification,
    AnomalyInitialVerification,
    AnomalyStage,
    AnomalyStatus,
    AnomalyStatusHistory,
    ObservationResolutionPath,
)
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
        self.task_user = User.objects.create_user(
            username="mechi",
            email="mechi@example.com",
            password="secret123",
        )
        self.other_task_user = User.objects.create_user(
            username="other_task_user",
            email="other_task_user@example.com",
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
        anomaly = Anomaly.objects.create(
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
        AnomalyInitialVerification.objects.create(
            anomaly=anomaly,
            verified_by=self.admin,
            verified_at=timezone.now(),
            summary="Verificacion inicial registrada.",
            created_by=self.admin,
            updated_by=self.admin,
        )
        AnomalyClassification.objects.create(
            anomaly=anomaly,
            classified_by=self.admin,
            classified_at=timezone.now(),
            requires_action_plan=True,
            requires_effectiveness_verification=True,
            summary="Anomalia clasificada para tratamiento.",
            created_by=self.admin,
            updated_by=self.admin,
        )
        return anomaly

    def _create_observation_anomaly(self, *, code: str = "20269010"):
        anomaly = self._create_anomaly(
            code=code,
            title="Anomalia Observacion",
            reporter=self.reporter_one,
            area=self.area_one,
            detected_at=timezone.now(),
        )
        anomaly.classification_summary = "Observacion"
        anomaly.save(update_fields=["classification_summary"])
        classification = anomaly.classification
        classification.summary = "Observacion"
        classification.save(update_fields=["summary"])
        return anomaly

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

    def test_candidates_reject_invalid_date_filters(self):
        response = self.client.get("/api/v1/actions/treatments/candidates/?date_from=not-a-date")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_from", response.data)

    def test_action_items_reject_invalid_completed_on_filter(self):
        response = self.client.get("/api/v1/actions/items/?completed_on=not-a-date")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed_on", response.data)

    def test_open_options_return_open_treatments_available_for_candidate(self):
        response = self.client.get(f"/api/v1/actions/treatments/open-options/?anomaly={self.anomaly_three.pk}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        treatment_ids = {item["id"] for item in response.data}
        self.assertIn(str(self.treatment_one.pk), treatment_ids)
        self.assertIn(str(self.treatment_two.pk), treatment_ids)

    def test_create_rejects_new_treatment_when_open_treatment_is_available(self):
        response = self.client.post(
            "/api/v1/actions/treatments/",
            {"primary_anomaly": str(self.anomaly_three.pk), "status": "pending"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("primary_anomaly", response.data)
        self.assertEqual(Treatment.objects.count(), 2)
        self.assertFalse(TreatmentAnomaly.objects.filter(anomaly=self.anomaly_three).exists())

    def test_create_allows_explicit_new_treatment_when_open_treatment_is_available(self):
        response = self.client.post(
            "/api/v1/actions/treatments/",
            {
                "primary_anomaly": str(self.anomaly_three.pk),
                "status": "pending",
                "force_create_new": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Treatment.objects.count(), 3)
        self.assertTrue(
            TreatmentAnomaly.objects.filter(
                treatment_id=response.data["id"],
                anomaly=self.anomaly_three,
                is_primary=True,
            ).exists()
        )

    def test_observation_anomaly_is_available_for_treatment_until_path_is_selected(self):
        anomaly = self._create_observation_anomaly()

        candidates_response = self.client.get("/api/v1/actions/treatments/candidates/")
        self.assertEqual(candidates_response.status_code, status.HTTP_200_OK)
        candidate_ids = {item["id"] for item in candidates_response.data["results"]}
        self.assertIn(str(anomaly.pk), candidate_ids)

        create_response = self.client.post(
            "/api/v1/actions/treatments/",
            {
                "primary_anomaly": str(anomaly.pk),
                "status": "pending",
                "force_create_new": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.observation_resolution_path, ObservationResolutionPath.TREATMENT)

        observation_response = self.client.get("/api/v1/anomalies/immediate-actions/")
        self.assertEqual(observation_response.status_code, status.HTTP_200_OK)
        observation_ids = {item["id"] for item in observation_response.data["results"]}
        self.assertNotIn(str(anomaly.pk), observation_ids)

        save_observation_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/immediate-action/",
            {
                "responsible": str(self.admin.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Intento de Observacion",
                "actions_taken": "Acciones tomadas",
            },
            format="json",
        )
        self.assertEqual(save_observation_response.status_code, status.HTTP_400_BAD_REQUEST)

        history = AnomalyStatusHistory.objects.filter(
            anomaly=anomaly,
            comment__icontains="Camino elegido: TREATMENT",
        ).latest("created_at")
        self.assertIn("Camino nuevo: TREATMENT", history.evidence_note)

    def test_observation_managed_as_observation_is_not_available_for_treatment(self):
        anomaly = self._create_observation_anomaly(code="20269011")

        observation_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/immediate-action/",
            {
                "responsible": str(self.admin.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Observacion inicial",
                "actions_taken": "Acciones tomadas",
            },
            format="json",
        )

        self.assertEqual(observation_response.status_code, status.HTTP_200_OK)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.observation_resolution_path, ObservationResolutionPath.OBSERVATION)

        candidates_response = self.client.get("/api/v1/actions/treatments/candidates/")
        self.assertEqual(candidates_response.status_code, status.HTTP_200_OK)
        candidate_ids = {item["id"] for item in candidates_response.data["results"]}
        self.assertNotIn(str(anomaly.pk), candidate_ids)

        create_response = self.client.post(
            "/api/v1/actions/treatments/",
            {
                "primary_anomaly": str(anomaly.pk),
                "status": "pending",
                "force_create_new": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("primary_anomaly", create_response.data)

    def test_tasks_history_for_participant_only_returns_own_tasks(self):
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )
        own_task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-001",
            title="Tarea de Mechi",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )
        other_task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-002",
            title="Tarea de otro usuario",
            responsible=self.other_task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_authenticate(user=self.task_user)
        response = self.client.get("/api/v1/actions/treatments/tasks-history/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(own_task.pk), task_ids)
        self.assertNotIn(str(other_task.pk), task_ids)

    def test_admin_tasks_history_can_return_all_tasks(self):
        own_task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-003",
            title="Tarea visible admin 1",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )
        other_task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-004",
            title="Tarea visible admin 2",
            responsible=self.other_task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/v1/actions/treatments/tasks-history/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(own_task.pk), task_ids)
        self.assertIn(str(other_task.pk), task_ids)

    def test_tasks_history_rejects_invalid_completed_on_filter(self):
        response = self.client.get(
            "/api/v1/actions/treatments/tasks-history/?completed_on=not-a-date"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed_on", response.data)

    def test_task_status_change_requires_evidence_note(self):
        task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-005",
            title="Tarea requiere evidencia",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_authenticate(user=self.task_user)
        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/",
            {"status": "in_progress", "evidence_note": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("evidence_note", response.data)
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")

    def test_task_status_change_with_evidence_note_registers_anomaly_history(self):
        task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-006",
            title="Tarea con evidencia",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_authenticate(user=self.task_user)
        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/",
            {"status": "in_progress", "evidence_note": "Se inicia con material segregado."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")
        history = AnomalyStatusHistory.objects.filter(
            anomaly=self.anomaly_one,
            comment__icontains=task.code,
        ).latest("created_at")
        self.assertIn("de estado pending a estado in_progress", history.comment)
        self.assertEqual(history.evidence_note, "Se inicia con material segregado.")

    def test_multiple_task_status_changes_register_independent_evidence_notes(self):
        task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-007",
            title="Tarea multiples cambios",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_authenticate(user=self.task_user)
        first_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/",
            {"status": "in_progress", "evidence_note": "Primera evidencia."},
            format="json",
        )
        second_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/",
            {"status": "completed", "evidence_note": "Segunda evidencia."},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        notes = list(
            AnomalyStatusHistory.objects.filter(
                anomaly=self.anomaly_one,
                comment__icontains=task.code,
            )
            .order_by("created_at")
            .values_list("evidence_note", flat=True)
        )
        self.assertEqual(notes, ["Primera evidencia.", "Segunda evidencia."])

    def test_can_add_treatment_task_before_effectiveness_assignment(self):
        root_cause = TreatmentRootCause.objects.create(
            treatment=self.treatment_one,
            sequence=1,
            description="Causa para tarea",
            created_by=self.admin,
            updated_by=self.admin,
        )
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )

        response = self.client.post(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/",
            {
                "title": "Tarea antes de evaluacion",
                "description": "Descripcion de la tarea",
                "root_cause": str(root_cause.pk),
                "responsible": str(self.task_user.pk),
                "execution_date": timezone.localdate().isoformat(),
                "status": "pending",
                "anomaly_ids": [str(self.anomaly_one.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TreatmentTask.objects.filter(treatment=self.treatment_one).count(), 1)

    def test_add_treatment_task_requires_convoked_responsible(self):
        root_cause = TreatmentRootCause.objects.create(
            treatment=self.treatment_one,
            sequence=1,
            description="Causa para responsable no convocado",
            created_by=self.admin,
            updated_by=self.admin,
        )

        response = self.client.post(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/",
            {
                "title": "Tarea sin responsable convocado",
                "description": "Descripcion de la tarea",
                "root_cause": str(root_cause.pk),
                "responsible": str(self.other_task_user.pk),
                "execution_date": timezone.localdate().isoformat(),
                "status": "pending",
                "anomaly_ids": [str(self.anomaly_one.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("responsible", response.data)
        self.assertEqual(TreatmentTask.objects.filter(treatment=self.treatment_one).count(), 0)

    def test_save_analysis_requires_effectiveness_evaluation_date(self):
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )

        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis con responsable pero sin fecha.",
                "effectiveness_responsible": str(self.task_user.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effectiveness_evaluation_date", response.data)

    def test_method_and_observations_can_be_saved_as_editable_analysis_draft(self):
        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis editable antes de cargar evidencias y causas.",
            },
            format="json",
        )
        detail_response = self.client.get(f"/api/v1/actions/treatments/{self.treatment_one.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["method_used"], "five_whys")
        self.assertEqual(
            detail_response.data["observations"],
            "Analisis editable antes de cargar evidencias y causas.",
        )

    def test_save_analysis_requires_effectiveness_responsible(self):
        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis con fecha pero sin responsable.",
                "effectiveness_evaluation_date": timezone.localdate().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effectiveness_responsible", response.data)

    def test_effectiveness_responsible_must_be_treatment_participant(self):
        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis con usuario no convocado.",
                "effectiveness_evaluation_date": timezone.localdate().isoformat(),
                "effectiveness_responsible": str(self.other_task_user.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effectiveness_responsible", response.data)

    def test_effectiveness_evaluation_fields_are_persisted_in_treatment_detail(self):
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )
        evaluation_date = timezone.localdate().isoformat()

        update_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis con evaluacion de eficacia.",
                "effectiveness_evaluation_date": evaluation_date,
                "effectiveness_responsible": str(self.task_user.pk),
            },
            format="json",
        )
        detail_response = self.client.get(f"/api/v1/actions/treatments/{self.treatment_one.pk}/")

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["effectiveness_evaluation_date"], evaluation_date)
        self.assertEqual(detail_response.data["effectiveness_responsible"]["id"], str(self.task_user.pk))

    def test_effectiveness_evaluation_update_registers_anomaly_history_detail(self):
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )
        evaluation_date = timezone.localdate().isoformat()

        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis con historial de eficacia.",
                "effectiveness_evaluation_date": evaluation_date,
                "effectiveness_responsible": str(self.task_user.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = AnomalyStatusHistory.objects.filter(
            anomaly=self.anomaly_one,
            comment__icontains="evaluacion de eficacia",
        ).latest("created_at")
        self.assertIn(evaluation_date, history.comment)
        self.assertIn(self.task_user.full_name, history.comment)

    def test_effectiveness_evaluation_history_uses_primary_anomaly_if_link_is_missing(self):
        TreatmentAnomaly.objects.filter(treatment=self.treatment_one).delete()
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )
        evaluation_date = timezone.localdate().isoformat()

        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis con historial en anomalia principal.",
                "effectiveness_evaluation_date": evaluation_date,
                "effectiveness_responsible": str(self.task_user.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = AnomalyStatusHistory.objects.filter(
            anomaly=self.anomaly_one,
            comment__icontains="evaluacion de eficacia",
        ).latest("created_at")
        self.assertIn(evaluation_date, history.comment)

    def _prepare_treatment_for_validation(self, *, treatment=None, responsible=None, scheduled_for=None, task_status="completed"):
        treatment = treatment or self.treatment_one
        responsible = responsible or self.task_user
        TreatmentParticipant.objects.get_or_create(
            treatment=treatment,
            user=responsible,
            defaults={"created_by": self.admin, "updated_by": self.admin},
        )
        root_cause = TreatmentRootCause.objects.create(
            treatment=treatment,
            sequence=1,
            description="Causa validable",
            created_by=self.admin,
            updated_by=self.admin,
        )
        TreatmentTask.objects.create(
            treatment=treatment,
            root_cause=root_cause,
            code=f"{treatment.code}-TV01",
            title="Tarea validable",
            responsible=responsible,
            execution_date=timezone.localdate(),
            status=task_status,
            created_by=self.admin,
            updated_by=self.admin,
        )
        treatment.scheduled_for = scheduled_for or (timezone.now() - timedelta(days=1))
        treatment.effectiveness_evaluation_date = timezone.localdate()
        treatment.effectiveness_responsible = responsible
        treatment.status = "in_progress"
        treatment.save()
        return treatment

    def test_treatment_not_available_for_validation_if_scheduled_date_has_not_passed(self):
        treatment = self._prepare_treatment_for_validation(scheduled_for=timezone.now() + timedelta(days=1))
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("validation", response.data)

    def test_validation_ready_list_only_returns_ready_treatments_for_responsible_user(self):
        ready_treatment = self._prepare_treatment_for_validation(treatment=self.treatment_one, responsible=self.task_user)
        self._prepare_treatment_for_validation(treatment=self.treatment_two, responsible=self.other_task_user)
        self.client.force_authenticate(user=self.task_user)

        response = self.client.get("/api/v1/actions/treatments/?validation_ready=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(ready_treatment.pk)})

    def test_validation_ready_list_admin_can_see_all_ready_treatments(self):
        treatment_one = self._prepare_treatment_for_validation(treatment=self.treatment_one, responsible=self.task_user)
        treatment_two = self._prepare_treatment_for_validation(treatment=self.treatment_two, responsible=self.other_task_user)
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/v1/actions/treatments/?validation_ready=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(treatment_one.pk), str(treatment_two.pk)})

    def test_validation_ready_list_administrator_role_can_see_all_ready_treatments(self):
        role_admin, _ = Role.objects.get_or_create(code="ADMINISTRADOR", defaults={"name": "Administrador"})
        role_user = User.objects.create_user(
            username="role_admin",
            email="role_admin@example.com",
            password="secret123",
        )
        UserRoleScope.objects.create(
            user=role_user,
            role=role_admin,
            site=self.site,
            created_by=self.admin,
            updated_by=self.admin,
        )
        treatment_one = self._prepare_treatment_for_validation(treatment=self.treatment_one, responsible=self.task_user)
        treatment_two = self._prepare_treatment_for_validation(treatment=self.treatment_two, responsible=self.other_task_user)
        self.client.force_authenticate(user=role_user)

        response = self.client.get("/api/v1/actions/treatments/?validation_ready=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(treatment_one.pk), str(treatment_two.pk)})

    def test_treatment_not_available_for_validation_without_root_cause(self):
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.treatment_one.scheduled_for = timezone.now() - timedelta(days=1)
        self.treatment_one.effectiveness_evaluation_date = timezone.localdate()
        self.treatment_one.effectiveness_responsible = self.task_user
        self.treatment_one.save()
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/validation/",
            {"result": "effective"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("validation", response.data)

    def test_treatment_not_available_for_validation_if_root_cause_has_no_detail(self):
        treatment = self._prepare_treatment_for_validation()
        treatment.root_causes.update(description="")
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("validation", response.data)

    def test_treatment_not_available_for_validation_without_effectiveness_assignment(self):
        treatment = self._prepare_treatment_for_validation()
        treatment.effectiveness_evaluation_date = None
        treatment.effectiveness_responsible = None
        treatment.save()
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effectiveness_responsible", response.data)

    def test_treatment_not_available_for_validation_with_incomplete_tasks(self):
        treatment = self._prepare_treatment_for_validation(task_status="in_progress")
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("validation", response.data)

    def test_non_responsible_user_cannot_validate_treatment(self):
        treatment = self._prepare_treatment_for_validation()
        TreatmentParticipant.objects.create(
            treatment=treatment,
            user=self.other_task_user,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_authenticate(user=self.other_task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_responsible_can_validate_effective_and_close_treatment(self):
        treatment = self._prepare_treatment_for_validation()
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective", "comment": "Resultado conforme."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        treatment.refresh_from_db()
        self.assertEqual(treatment.status, "completed")
        self.assertEqual(treatment.effectiveness_validation_result, "effective")
        self.anomaly_one.refresh_from_db()
        self.assertEqual(self.anomaly_one.current_status, AnomalyStatus.CLOSED)
        self.assertEqual(self.anomaly_one.current_stage, AnomalyStage.CLOSURE)
        self.assertIsNotNone(self.anomaly_one.closed_at)

    def test_effective_validation_closes_all_linked_anomalies_and_registers_history(self):
        treatment = self._prepare_treatment_for_validation()
        TreatmentAnomaly.objects.create(
            treatment=treatment,
            anomaly=self.anomaly_two,
            is_primary=False,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective", "comment": "Resultado conforme."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.anomaly_one.refresh_from_db()
        self.anomaly_two.refresh_from_db()
        self.assertEqual(self.anomaly_one.current_status, AnomalyStatus.CLOSED)
        self.assertEqual(self.anomaly_two.current_status, AnomalyStatus.CLOSED)
        for anomaly in (self.anomaly_one, self.anomaly_two):
            self.assertTrue(
                AnomalyStatusHistory.objects.filter(
                    anomaly=anomaly,
                    comment__icontains="Anomalia cerrada automaticamente",
                    to_status=AnomalyStatus.CLOSED,
                    to_stage=AnomalyStage.CLOSURE,
                ).exists()
            )

    def test_effectively_closed_treatment_rejects_further_changes(self):
        treatment = self._prepare_treatment_for_validation()
        self.client.force_authenticate(user=self.task_user)
        validate_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective", "comment": "Resultado conforme."},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)

        update_response = self.client.patch(
            f"/api/v1/actions/treatments/{treatment.pk}/",
            {"observations": "Intento de cambio posterior."},
            format="json",
        )
        task_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/tasks/",
            {
                "title": "No deberia crearse",
                "description": "Tratamiento cerrado",
                "root_cause": str(treatment.root_causes.first().pk),
                "responsible": str(self.task_user.pk),
                "execution_date": timezone.localdate().isoformat(),
                "status": "pending",
                "anomaly_ids": [str(self.anomaly_one.pk)],
            },
            format="json",
        )
        revalidate_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "not_effective", "comment": "Intento posterior."},
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(task_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(revalidate_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anomaly_closed_by_effective_treatment_rejects_updates_and_transitions(self):
        treatment = self._prepare_treatment_for_validation()
        self.client.force_authenticate(user=self.task_user)
        validate_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective", "comment": "Resultado conforme."},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.admin)
        update_response = self.client.patch(
            f"/api/v1/anomalies/{self.anomaly_one.pk}/",
            {"title": "Cambio bloqueado"},
            format="json",
        )
        transition_response = self.client.post(
            f"/api/v1/anomalies/{self.anomaly_one.pk}/transition/",
            {
                "target_status": AnomalyStatus.REOPENED,
                "target_stage": AnomalyStage.CAUSE_ANALYSIS,
                "comment": "Intento de reapertura manual.",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(transition_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_responsible_can_validate_not_effective_and_reopen_treatment(self):
        treatment = self._prepare_treatment_for_validation()
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "not_effective", "comment": "Persisten desvios."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        treatment.refresh_from_db()
        self.assertEqual(treatment.status, "in_progress")
        self.assertEqual(treatment.effectiveness_validation_result, "not_effective")

    def test_treatment_validation_registers_anomaly_history(self):
        treatment = self._prepare_treatment_for_validation()
        self.client.force_authenticate(user=self.task_user)

        response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "effective", "comment": "Validacion documentada."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = AnomalyStatusHistory.objects.filter(
            anomaly=self.anomaly_one,
            comment__icontains="validacion de eficacia",
        ).latest("created_at")
        self.assertIn("resultado eficaz", history.comment)
        self.assertIn("Validacion documentada", history.comment)
