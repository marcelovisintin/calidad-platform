from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.actions.models import (
    Treatment,
    TreatmentAnomaly,
    TreatmentCodeSequence,
    TreatmentParticipant,
    TreatmentRootCause,
    TreatmentTask,
    TreatmentTaskStatus,
)
from apps.actions.services import can_manage_treatment, create_configured_treatment
from apps.actions.services.treatment_service import _next_treatment_code
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
from apps.notifications.models import NotificationRecipient


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
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
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
        self.severity = Severity.objects.create(code="NC", name="No Conformidad")
        self.observation_severity = Severity.objects.create(code="OBS", name="Observacion")
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
        anomaly.severity = self.observation_severity
        anomaly.save(update_fields=["classification_summary", "severity"])
        classification = anomaly.classification
        classification.summary = "Observacion"
        classification.save(update_fields=["summary"])
        return anomaly

    def test_candidates_include_anomalies_from_empty_pending_treatments(self):
        default_response = self.client.get("/api/v1/actions/treatments/candidates/")
        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        default_ids = {item["id"] for item in default_response.data["results"]}
        self.assertIn(str(self.anomaly_three.pk), default_ids)
        self.assertIn(str(self.anomaly_one.pk), default_ids)
        self.assertIn(str(self.anomaly_two.pk), default_ids)

        scoped_response = self.client.get(f"/api/v1/actions/treatments/candidates/?treatment={self.treatment_one.pk}")
        self.assertEqual(scoped_response.status_code, status.HTTP_200_OK)
        scoped_ids = {item["id"] for item in scoped_response.data["results"]}
        self.assertIn(str(self.anomaly_two.pk), scoped_ids)
        self.assertIn(str(self.anomaly_three.pk), scoped_ids)
        self.assertIn(str(self.anomaly_one.pk), scoped_ids)

    def test_candidates_exclude_linked_anomaly_after_treatment_work_starts(self):
        TreatmentRootCause.objects.create(
            treatment=self.treatment_one,
            sequence=1,
            description="Causa ya analizada",
            created_by=self.admin,
            updated_by=self.admin,
        )

        response = self.client.get("/api/v1/actions/treatments/candidates/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        candidate_ids = {item["id"] for item in response.data["results"]}
        self.assertNotIn(str(self.anomaly_one.pk), candidate_ids)
        self.assertIn(str(self.anomaly_two.pk), candidate_ids)

    def test_candidates_support_filters_for_anomaly_area_user_and_date(self):
        date_from = (timezone.localdate() - timedelta(days=4)).isoformat()
        date_to = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.get(
            "/api/v1/actions/treatments/candidates/"
            f"?treatment={self.treatment_one.pk}"
            "&anomaly=20269003"
            "&area=A01"
            f"&user={self.reporter_one.pk}"
            f"&date_from={date_from}"
            f"&date_to={date_to}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.anomaly_three.pk))

    def test_candidates_reject_invalid_date_filters(self):
        response = self.client.get("/api/v1/actions/treatments/candidates/?date_from=not-a-date")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_from", response.data)

    def test_admin_classification_conforms_locked_treatment_with_unique_responsible(self):
        previous_manager = User.objects.create_user(
            username="previous_manager",
            email="previous_manager@example.com",
            password="secret123",
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        self.anomaly_three.owner = previous_manager
        self.anomaly_three.save(update_fields=["owner", "updated_at"])
        primary = Anomaly.objects.create(
            code="20269020",
            title="No conformidad principal",
            description="Hallazgo principal para tratamiento conjunto",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area_one,
            reporter=self.reporter_one,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.admin,
            updated_by=self.admin,
        )

        candidates_response = self.client.get(
            f"/api/v1/actions/treatments/candidates/?anchor={primary.pk}"
        )
        candidate = next(
            item for item in candidates_response.data["results"]
            if item["id"] == str(self.anomaly_three.pk)
        )
        self.assertTrue(candidate["suggested_by_repetition"])

        response = self.client.patch(
            f"/api/v1/anomalies/{primary.pk}/",
            {
                "severity": str(self.severity.pk),
                "classification_responsible": str(self.task_user.pk),
                "treatment_related_anomalies": [str(self.anomaly_three.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        treatment = Treatment.objects.get(primary_anomaly=primary)
        self.assertEqual(treatment.responsible, self.task_user)
        self.assertEqual(treatment.anomaly_links.count(), 2)
        primary.refresh_from_db()
        self.anomaly_three.refresh_from_db()
        self.assertEqual(primary.owner, self.task_user)
        self.assertEqual(self.anomaly_three.owner, self.task_user)
        self.assertTrue(can_manage_treatment(self.task_user, treatment))
        self.assertFalse(can_manage_treatment(previous_manager, treatment))

    def test_admin_classification_reuses_pending_treatment_code_without_creating_another(self):
        primary = Anomaly.objects.create(
            code="20269022",
            title="Nueva NC para tratamiento existente",
            description="Debe reutilizar el tratamiento pendiente.",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area_one,
            reporter=self.reporter_one,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.admin,
            updated_by=self.admin,
        )
        treatment_count = Treatment.objects.count()

        response = self.client.patch(
            f"/api/v1/anomalies/{primary.pk}/",
            {
                "severity": str(self.severity.pk),
                "classification_responsible": str(self.task_user.pk),
                "treatment_related_anomalies": [str(self.anomaly_one.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Treatment.objects.count(), treatment_count)
        self.treatment_one.refresh_from_db()
        self.assertEqual(self.treatment_one.code, "TRT-2026-0001")
        self.assertEqual(self.treatment_one.responsible, self.task_user)
        self.assertTrue(TreatmentAnomaly.objects.filter(treatment=self.treatment_one, anomaly=primary).exists())
        self.assertFalse(Treatment.objects.filter(primary_anomaly=primary).exists())

    def test_admin_classification_consolidates_pending_codes_without_reusing_or_deleting_them(self):
        primary = Anomaly.objects.create(
            code="20269023",
            title="NC para consolidar borradores",
            description="Consolida dos tratamientos pendientes.",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area_one,
            reporter=self.reporter_one,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.admin,
            updated_by=self.admin,
        )
        treatment_count = Treatment.objects.count()

        response = self.client.patch(
            f"/api/v1/anomalies/{primary.pk}/",
            {
                "severity": str(self.severity.pk),
                "classification_responsible": str(self.task_user.pk),
                "treatment_related_anomalies": [
                    str(self.anomaly_one.pk),
                    str(self.anomaly_two.pk),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Treatment.objects.count(), treatment_count)
        self.treatment_one.refresh_from_db()
        self.treatment_two.refresh_from_db()
        self.assertEqual(self.treatment_one.status, "pending")
        self.assertEqual(self.treatment_two.status, "cancelled")
        self.assertIn("TRT-2026-0001", self.treatment_two.observations)
        self.assertEqual(
            set(self.treatment_one.anomaly_links.values_list("anomaly_id", flat=True)),
            {self.anomaly_one.pk, self.anomaly_two.pk, primary.pk},
        )
        self.assertFalse(self.treatment_two.anomaly_links.exists())
        self.assertEqual(
            set(Treatment.objects.values_list("code", flat=True)),
            {"TRT-2026-0001", "TRT-2026-0002"},
        )

    def test_treatment_numbering_continues_after_existing_highest_code(self):
        treatment = create_configured_treatment(
            primary_anomaly=self.anomaly_three,
            related_anomalies=[],
            responsible=self.task_user,
            user=self.admin,
        )

        self.assertEqual(treatment.code, "TRT-2026-0003")

    def test_treatment_number_is_not_consumed_when_transaction_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                discarded = create_configured_treatment(
                    primary_anomaly=self.anomaly_three,
                    related_anomalies=[],
                    responsible=self.task_user,
                    user=self.admin,
                )
                self.assertEqual(discarded.code, "TRT-2026-0003")
                raise RuntimeError("Se revierte la confirmacion completa")

        treatment = create_configured_treatment(
            primary_anomaly=self.anomaly_three,
            related_anomalies=[],
            responsible=self.task_user,
            user=self.admin,
        )

        self.assertEqual(treatment.code, "TRT-2026-0003")

    def test_concurrent_treatment_code_reservations_are_distinct_and_consecutive(self):
        barrier = Barrier(2)

        def reserve_in_separate_connection():
            close_old_connections()
            try:
                with transaction.atomic():
                    barrier.wait(timeout=10)
                    return _next_treatment_code()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = set(executor.map(lambda _: reserve_in_separate_connection(), range(2)))

        year = timezone.localdate().year
        self.assertEqual(codes, {f"TRT-{year}-0001", f"TRT-{year}-0002"})

        def clean_committed_counter():
            close_old_connections()
            try:
                TreatmentCodeSequence.objects.filter(year=year).delete()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(clean_committed_counter).result()

    def test_admin_correction_requires_reason_and_is_blocked_after_work_starts(self):
        self.anomaly_three.owner = self.task_user
        self.anomaly_three.save(update_fields=["owner", "updated_at"])
        treatment = create_configured_treatment(
            primary_anomaly=self.anomaly_three,
            related_anomalies=[],
            responsible=self.task_user,
            user=self.admin,
        )
        extra = self._create_anomaly(
            code="20269021",
            title="Anomalia para correccion",
            reporter=self.reporter_two,
            area=self.area_two,
            detected_at=timezone.now(),
        )

        direct_add = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/anomalies/",
            {"anomaly": str(extra.pk)},
            format="json",
        )
        self.assertEqual(direct_add.status_code, status.HTTP_403_FORBIDDEN)

        correction = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/reconfigure/",
            {
                "responsible": str(self.task_user.pk),
                "related_anomalies": [str(extra.pk)],
                "reason": "Se confirma relacion durante la revision administrativa.",
            },
            format="json",
        )
        self.assertEqual(correction.status_code, status.HTTP_200_OK)
        self.assertTrue(TreatmentAnomaly.objects.filter(treatment=treatment, anomaly=extra).exists())

        TreatmentParticipant.objects.create(
            treatment=treatment,
            user=self.reporter_two,
            role="convoked",
            created_by=self.task_user,
            updated_by=self.task_user,
        )
        blocked = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/reconfigure/",
            {
                "responsible": str(self.task_user.pk),
                "related_anomalies": [],
                "reason": "Intento posterior al inicio.",
            },
            format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_public_create_is_blocked_because_quality_conforms_treatment_during_classification(self):
        response = self.client.post(
            "/api/v1/actions/treatments/",
            {"primary_anomaly": str(self.anomaly_three.pk), "status": "pending"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Treatment.objects.count(), 2)
        self.assertFalse(TreatmentAnomaly.objects.filter(anomaly=self.anomaly_three).exists())

    def test_public_create_cannot_be_forced(self):
        response = self.client.post(
            "/api/v1/actions/treatments/",
            {
                "primary_anomaly": str(self.anomaly_three.pk),
                "status": "pending",
                "force_create_new": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Treatment.objects.count(), 2)

    def test_classification_responsible_cannot_create_but_can_manage_assigned_treatment(self):
        self.anomaly_three.owner = self.task_user
        self.anomaly_three.updated_by = self.admin
        self.anomaly_three.save(update_fields=["owner", "updated_by", "updated_at"])
        create_response = self.client.post(
            "/api/v1/actions/treatments/",
            {
                "primary_anomaly": str(self.anomaly_three.pk),
                "status": "pending",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        treatment = Treatment.objects.create(
            code="TRT-2026-0099",
            primary_anomaly=self.anomaly_three,
            responsible=self.task_user,
            status="pending",
            created_by=self.admin,
            updated_by=self.admin,
        )
        TreatmentAnomaly.objects.create(
            treatment=treatment,
            anomaly=self.anomaly_three,
            is_primary=True,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_authenticate(user=self.task_user)

        detail_response = self.client.get(f"/api/v1/actions/treatments/{treatment.pk}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertTrue(detail_response.data["can_manage"])

    def test_treatment_responsible_can_list_and_invite_all_active_users(self):
        inactive_user = User.objects.create_user(
            username="inactive_candidate",
            email="inactive_candidate@example.com",
            password="secret123",
            is_active=False,
        )
        self.anomaly_three.owner = self.task_user
        self.anomaly_three.updated_by = self.admin
        self.anomaly_three.save(update_fields=["owner", "updated_by", "updated_at"])
        self.treatment_one.responsible = self.task_user
        self.treatment_one.primary_anomaly.owner = self.task_user
        self.treatment_one.primary_anomaly.save(update_fields=["owner", "updated_at"])
        self.treatment_one.save(update_fields=["responsible", "updated_at"])
        self.client.force_authenticate(user=self.task_user)
        treatment_id = self.treatment_one.pk

        options_response = self.client.get(
            f"/api/v1/actions/treatments/{treatment_id}/participant-options/"
        )

        self.assertEqual(options_response.status_code, status.HTTP_200_OK)
        option_ids = {item["id"] for item in options_response.data}
        self.assertIn(str(self.reporter_one.pk), option_ids)
        self.assertIn(str(self.reporter_two.pk), option_ids)
        self.assertIn(str(self.other_task_user.pk), option_ids)
        self.assertNotIn(str(inactive_user.pk), option_ids)

        invite_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment_id}/participants/",
            {
                "user": str(self.reporter_two.pk),
                "role": "convoked",
                "note": "Convocado desde la lista completa.",
            },
            format="json",
        )
        self.assertEqual(invite_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            TreatmentParticipant.objects.filter(
                treatment_id=treatment_id,
                user=self.reporter_two,
            ).exists()
        )

        scheduled_for = timezone.now() + timedelta(days=2)
        confirm_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment_id}/confirm-convocation/",
            {
                "scheduled_for": scheduled_for.isoformat(),
                "treatment_location": "Sala de Calidad",
            },
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(confirm_response.data["convocation_confirmed_at"])
        self.assertEqual(confirm_response.data["convocation_confirmed_by"]["id"], str(self.task_user.pk))
        self.assertEqual(confirm_response.data["status"], "scheduled")

        blocked_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment_id}/participants/",
            {
                "user": str(self.other_task_user.pk),
                "role": "convoked",
                "note": "Intento posterior a la confirmacion.",
            },
            format="json",
        )
        self.assertEqual(blocked_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            TreatmentParticipant.objects.filter(
                treatment_id=treatment_id,
                user=self.other_task_user,
            ).exists()
        )

        agenda_change = self.client.patch(
            f"/api/v1/actions/treatments/{treatment_id}/",
            {"scheduled_for": (scheduled_for + timedelta(days=1)).isoformat()},
            format="json",
        )
        self.assertEqual(agenda_change.status_code, status.HTTP_400_BAD_REQUEST)

    def test_convoked_or_facilitator_with_assign_permission_cannot_manage_treatment(self):
        assign_permission = Permission.objects.get(
            content_type__app_label="actions",
            codename="assign_action",
        )
        self.task_user.user_permissions.add(assign_permission)
        participant = TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            role="convoked",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_authenticate(user=self.task_user)

        for participant_role in ("convoked", "facilitator"):
            with self.subTest(participant_role=participant_role):
                participant.role = participant_role
                participant.save(update_fields=["role", "updated_at"])
                detail_response = self.client.get(f"/api/v1/actions/treatments/{self.treatment_one.pk}/")
                update_response = self.client.patch(
                    f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
                    {"observations": "Cambio no autorizado."},
                    format="json",
                )

                self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
                self.assertFalse(detail_response.data["can_manage"])
                self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reporter_with_assign_permission_has_read_only_treatment_access(self):
        assign_permission = Permission.objects.get(
            content_type__app_label="actions",
            codename="assign_action",
        )
        self.reporter_one.user_permissions.add(assign_permission)
        self.client.force_authenticate(user=self.reporter_one)

        detail_response = self.client.get(f"/api/v1/actions/treatments/{self.treatment_one.pk}/")
        update_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {"treatment_location": "Cambio no autorizado"},
            format="json",
        )

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertFalse(detail_response.data["can_manage"])
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_task_responsible_only_updates_status_and_adds_own_evidence(self):
        TreatmentParticipant.objects.create(
            treatment=self.treatment_one,
            user=self.task_user,
            role="convoked",
            created_by=self.admin,
            updated_by=self.admin,
        )
        task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-PERM-001",
            title="Tarea asignada",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_authenticate(user=self.task_user)

        forbidden_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/",
            {"title": "Titulo modificado"},
            format="json",
        )
        status_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/",
            {"status": "in_progress", "evidence_note": "Inicio de la tarea."},
            format="json",
        )
        evidence_response = self.client.post(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/tasks/{task.pk}/evidences/",
            {
                "file": SimpleUploadedFile("evidencia.txt", b"evidencia", content_type="text/plain"),
                "note": "Evidencia propia.",
            },
            format="multipart",
        )

        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertFalse(status_response.data["can_manage"])
        self.assertTrue(status_response.data["can_update_status"])
        self.assertEqual(evidence_response.status_code, status.HTTP_201_CREATED)

    def test_unassigned_middle_manager_cannot_manage_treatments(self):
        quality_user = User.objects.create_user(
            username="quality_manager",
            email="quality_manager@example.com",
            password="secret123",
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        self.client.force_authenticate(user=quality_user)

        list_response = self.client.get("/api/v1/actions/treatments/")
        update_response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_two.pk}/",
            {"treatment_location": "Sala Calidad"},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 0)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_observation_requires_trt_classification_before_treatment(self):
        anomaly = self._create_observation_anomaly()

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

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        anomaly.refresh_from_db()
        self.assertIsNone(anomaly.observation_resolution_path)

        observation_response = self.client.get("/api/v1/anomalies/immediate-actions/")
        self.assertEqual(observation_response.status_code, status.HTTP_200_OK)
        observation_ids = {item["id"] for item in observation_response.data["results"]}
        self.assertIn(str(anomaly.pk), observation_ids)

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

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_observation_trt_is_available_and_becomes_treatment_path_when_linked(self):
        anomaly = self._create_observation_anomaly(code="20269012")

        mark_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.admin.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Observacion plausible de tratamiento.",
                "requires_treatment": True,
            },
            format="json",
        )

        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mark_response.data["observation_resolution_path"], ObservationResolutionPath.TREATMENT_PENDING)
        self.assertEqual(mark_response.data["severity"]["id"], str(self.observation_severity.pk))
        self.assertEqual(mark_response.data["code"], "20269012-OBS")

        candidates_response = self.client.get("/api/v1/actions/treatments/candidates/")
        candidate_ids = {item["id"] for item in candidates_response.data["results"]}
        self.assertIn(str(anomaly.pk), candidate_ids)

        treatment = create_configured_treatment(
            primary_anomaly=self.anomaly_three,
            related_anomalies=[anomaly],
            responsible=self.admin,
            user=self.admin,
        )

        self.assertTrue(TreatmentAnomaly.objects.filter(treatment=treatment, anomaly=anomaly).exists())
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.observation_resolution_path, ObservationResolutionPath.TREATMENT)
        self.assertEqual(anomaly.severity_id, self.observation_severity.pk)
        self.assertEqual(anomaly.code, "20269012-OBS")

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
        completed_task = TreatmentTask.objects.create(
            treatment=self.treatment_one,
            code="TRT-TASK-COMPLETED-001",
            title="Tarea completada de Mechi",
            responsible=self.task_user,
            execution_date=timezone.localdate(),
            status=TreatmentTaskStatus.COMPLETED,
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_authenticate(user=self.task_user)
        response = self.client.get("/api/v1/actions/treatments/tasks-history/")
        completed_response = self.client.get("/api/v1/actions/treatments/tasks-history/?status=completed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(own_task.pk), task_ids)
        self.assertNotIn(str(other_task.pk), task_ids)
        self.assertNotIn(str(completed_task.pk), task_ids)
        self.assertEqual(completed_response.status_code, status.HTTP_200_OK)
        completed_task_ids = {item["id"] for item in completed_response.data["results"]}
        self.assertEqual(completed_task_ids, {str(completed_task.pk)})

    def test_admin_tasks_history_only_returns_tasks_assigned_to_admin(self):
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
        self.assertNotIn(str(own_task.pk), task_ids)
        self.assertNotIn(str(other_task.pk), task_ids)

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
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TreatmentTask.objects.filter(treatment=self.treatment_one).count(), 1)
        self.assertFalse(TreatmentTask.objects.get(treatment=self.treatment_one).anomaly_links.exists())

    def test_add_treatment_task_accepts_active_responsible_without_invitation(self):
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
                "title": "Tarea con responsable no convocado",
                "description": "Descripcion de la tarea",
                "root_cause": str(root_cause.pk),
                "responsible": str(self.other_task_user.pk),
                "execution_date": timezone.localdate().isoformat(),
                "status": "pending",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = TreatmentTask.objects.get(treatment=self.treatment_one)
        self.assertEqual(task.responsible, self.other_task_user)

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

    def test_active_middle_manager_can_be_effectiveness_responsible_without_invitation(self):
        evaluation_date = timezone.localdate().isoformat()

        response = self.client.patch(
            f"/api/v1/actions/treatments/{self.treatment_one.pk}/",
            {
                "method_used": "five_whys",
                "observations": "Analisis asignado a mando medio no convocado.",
                "effectiveness_evaluation_date": evaluation_date,
                "effectiveness_responsible": str(self.task_user.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["effectiveness_responsible"]["id"], str(self.task_user.pk))

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

    def test_validation_ready_list_admin_only_sees_own_assignments(self):
        treatment_one = self._prepare_treatment_for_validation(treatment=self.treatment_one, responsible=self.task_user)
        treatment_two = self._prepare_treatment_for_validation(treatment=self.treatment_two, responsible=self.other_task_user)
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/v1/actions/treatments/?validation_ready=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, set())

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
        self.assertTrue(
            NotificationRecipient.objects.filter(
                user=self.task_user,
                notification__template_code="treatment_closed",
                notification__source_id=treatment.pk,
            ).exists()
        )
        self.assertTrue(
            NotificationRecipient.objects.filter(
                user=self.reporter_one,
                notification__template_code="anomalies_closed_by_treatment",
                notification__source_id=treatment.pk,
            ).exists()
        )

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

        revalidate_response = self.client.post(
            f"/api/v1/actions/treatments/{treatment.pk}/validation/",
            {"result": "not_effective", "comment": "Intento posterior."},
            format="json",
        )

        self.client.force_authenticate(user=self.admin)
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
            },
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
        self.assertTrue(
            NotificationRecipient.objects.filter(
                user=self.task_user,
                notification__template_code="treatment_not_effective",
                notification__source_id=treatment.pk,
            ).exists()
        )

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
