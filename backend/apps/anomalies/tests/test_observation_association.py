from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from apps.accounts.models import User
from apps.anomalies.models import (
    Anomaly, AnomalyAttachment, AnomalyImmediateAction, AnomalyStage, AnomalyStatus,
    ObservationAction, ObservationResolutionPath,
)
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site
from apps.notifications.models import Notification, NotificationRecipient
from apps.notifications.services.due_eligibility import current_due_date
from apps.notifications.services.notification_service import notify_finding_management_assigned


class ObservationAssociationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="quality", email="quality@example.com", password="secret")
        self.manager = User.objects.create_user(username="manager", access_level="mando_medio_activo",
                                                 email="manager@example.com", email_notifications_enabled=True)
        self.reporter = User.objects.create_user(username="reporter", email="reporter@example.com")
        self.site = Site.objects.create(code="S", name="Sitio")
        self.area = Area.objects.create(code="A", name="Area", site=self.site)
        self.kind = AnomalyType.objects.create(code="T", name="Tipo")
        self.origin = AnomalyOrigin.objects.create(code="O", name="Origen")
        self.priority = Priority.objects.create(code="P", name="Prioridad")
        self.obs = Severity.objects.create(code="OBS", name="Observacion")
        self.nc = Severity.objects.create(code="NC", name="No Conformidad")
        self.client.force_authenticate(self.admin)
        self.root = self.make_anomaly("ROOT-OBS", severity=self.obs, owner=self.manager,
                                      current_stage=AnomalyStage.CLASSIFICATION, current_status=AnomalyStatus.IN_EVALUATION,
                                      observation_resolution_path=ObservationResolutionPath.OBSERVATION)
        AnomalyImmediateAction.objects.create(anomaly=self.root, responsible=self.manager,
                                               action_date=timezone.localdate() - timedelta(days=1),
                                               observation="Causa comun", created_by=self.admin)
        self.source = self.make_anomaly("SOURCE")

    def make_anomaly(self, code, **kwargs):
        return Anomaly.objects.create(code=code, title=code, description="Hallazgo",
                                      site=self.site, area=self.area, reporter=self.reporter,
                                      anomaly_type=self.kind, anomaly_origin=self.origin, priority=self.priority, detected_at=timezone.now(),
                                      created_by=self.admin, **kwargs)

    def associate(self, source=None, target=None, **kwargs):
        return self.client.post(f"/api/v1/anomalies/{(source or self.source).pk}/associate-observation/",
                                {"observation": str((target or self.root).pk), "reason": "Misma causa y acciones aplicables", **kwargs},
                                format="json")

    def create_action(self):
        response = self.client.post(f"/api/v1/anomalies/{self.root.pk}/observation/actions/", {
            "detail": "Corregir el proceso", "estimated_completion_date": timezone.localdate().isoformat(),
            "effectiveness_due_date": timezone.localdate().isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def complete(self, action_id):
        return self.client.post(f"/api/v1/anomalies/{self.root.pk}/observation/actions/{action_id}/complete/", {
            "completed_at": timezone.localdate().isoformat(), "evidence_note": "Se corrigio y verifico el proceso",
        }, format="json")

    def verify(self, effective=True, covered=None):
        self.client.force_authenticate(self.manager)
        return self.client.post(f"/api/v1/anomalies/{self.root.pk}/observation/effectiveness/", {
            "effectiveness_verified_at": timezone.now().isoformat(), "effectiveness_is_effective": effective,
            "effectiveness_comment": "Resultado comprobado en los hallazgos", "covered_anomalies": covered or [],
        }, format="json")

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_association_classifies_and_preserves_deadlines_without_duplicate_tasks(self):
        self.source.due_at = timezone.now() - timedelta(days=3)
        self.source.save()
        notify_finding_management_assigned(anomaly=self.root, responsible=self.manager, actor=self.admin)
        response = self.associate()
        self.assertEqual(response.status_code, 200, response.data)
        self.source.refresh_from_db()
        self.assertEqual(self.source.severity_id, self.obs.pk)
        self.assertEqual(self.source.owner_id, self.manager.pk)
        self.assertEqual(self.source.observation_parent_id, self.root.pk)
        self.assertEqual(self.source.deadline, self.root.deadline)
        self.assertTrue(self.source.is_overdue)
        self.assertEqual(self.source.due_at.date(), (timezone.now() - timedelta(days=3)).date())
        self.assertFalse(AnomalyImmediateAction.objects.filter(anomaly=self.source).exists())
        self.assertFalse(ObservationAction.objects.filter(anomaly=self.source).exists())
        self.assertFalse(response.data["can_modify_classification"])
        notes = Notification.objects.filter(template_code="observation_anomaly_associated")
        self.assertEqual(notes.count(), 1)
        self.assertEqual(set(notes.first().recipients.values_list("user_id", flat=True)), {self.manager.pk})
        self.assertTrue(self.source.status_history.filter(evidence_note__contains="Fecha limite anterior:").exists())
        self.assertEqual(self.associate().status_code, 400)
        self.assertEqual(notes.count(), 1)
        listing = self.client.get("/api/v1/anomalies/immediate-actions/")
        self.assertEqual([item["id"] for item in listing.data["results"]], [str(self.root.pk)])
        tracking = self.client.get(f"/api/v1/anomalies/{self.source.pk}/")
        self.assertEqual(tracking.data["observation_parent"]["id"], str(self.root.pk))

    def test_invalid_sources_and_targets_are_rejected(self):
        for field, value in [("current_status", "closed"), ("current_status", "cancelled"),
                             ("severity", self.nc), ("current_stage", AnomalyStage.EXECUTION_AND_FOLLOW_UP)]:
            original = getattr(self.source, field)
            setattr(self.source, field, value)
            self.source.save()
            with self.subTest(field=field, value=value):
                self.assertEqual(self.associate().status_code, 400)
            setattr(self.source, field, original)
            self.source.save()
        self.assertEqual(self.associate(reason="  ").status_code, 400)
        self.assertEqual(self.associate(source=self.root).status_code, 400)
        self.root.observation_resolution_path = ObservationResolutionPath.TREATMENT_PENDING
        self.root.save()
        self.assertEqual(self.associate().status_code, 400)
        self.root.observation_resolution_path = ObservationResolutionPath.OBSERVATION
        self.root.classification_summary = "Observacion"
        self.root.severity = self.nc
        self.root.save()
        self.assertEqual(self.associate().status_code, 400)

    def test_non_admin_cannot_associate_or_enumerate_targets(self):
        self.client.force_authenticate(self.reporter)
        self.assertEqual(self.associate().status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/anomalies/{self.source.pk}/observation-options/").status_code, 403)

    def test_progress_and_effective_closure_are_shared_and_require_exact_coverage(self):
        self.assertEqual(self.associate().status_code, 200)
        action_id = self.create_action()
        self.source.refresh_from_db()
        self.assertEqual(self.source.current_status, "in_treatment")
        self.assertEqual(self.complete(action_id).status_code, 200)
        self.source.refresh_from_db()
        self.assertEqual(self.source.current_status, "pending_verification")
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(self.verify(covered=[str(self.root.pk)]).status_code, 400)
        response = self.verify(covered=[str(self.root.pk), str(self.source.pk)])
        self.assertEqual(response.status_code, 200, response.data)
        self.source.refresh_from_db()
        self.root.refresh_from_db()
        self.assertEqual(self.source.current_status, "closed")
        self.assertEqual(self.source.closed_at, self.root.closed_at)
        self.assertEqual(self.root.effectiveness_checks.count(), 1)
        self.assertEqual(self.source.effectiveness_checks.count(), 0)
        self.assertIn(self.source.code, self.root.immediate_action.effectiveness_comment)

    def test_not_effective_leaves_all_findings_open_and_new_actions_keep_unique_workflow(self):
        self.assertEqual(self.associate().status_code, 200)
        action_id = self.create_action()
        self.assertEqual(self.complete(action_id).status_code, 200)
        self.assertEqual(self.verify(effective=False).status_code, 200)
        self.source.refresh_from_db()
        self.assertEqual(self.source.current_status, "in_treatment")
        self.create_action()
        self.assertEqual(ObservationAction.objects.filter(anomaly=self.root).count(), 2)
        self.assertFalse(ObservationAction.objects.filter(anomaly=self.source).exists())

    def test_pending_verification_and_closed_targets_do_not_accept_new_findings(self):
        action_id = self.create_action()
        self.assertEqual(self.complete(action_id).status_code, 200)
        self.assertEqual(self.associate().status_code, 400)
        options = self.client.get(f"/api/v1/anomalies/{self.source.pk}/observation-options/")
        self.assertEqual(options.data, [])
        self.assertEqual(self.verify().status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.associate().status_code, 400)

    def test_linked_finding_cannot_create_independent_actions_or_close_group_manually(self):
        self.assertEqual(self.associate().status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/anomalies/{self.source.pk}/observation/actions/", {
            "detail": "Duplicada", "estimated_completion_date": timezone.localdate().isoformat(),
            "effectiveness_due_date": timezone.localdate().isoformat(),
        }, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/v1/anomalies/{self.root.pk}/transition/", {
            "target_stage": "closure", "comment": "Intento sin verificar conjunto",
        }, format="json").status_code, 400)

    def test_source_with_own_work_cannot_be_merged_and_group_cannot_be_nested(self):
        AnomalyImmediateAction.objects.create(anomaly=self.source, responsible=self.manager,
                                               action_date=timezone.localdate(), observation="Trabajo propio")
        self.assertEqual(self.associate().status_code, 400)
        self.source.immediate_action.delete()
        self.assertEqual(self.associate().status_code, 200)
        other = self.make_anomaly("OTHER")
        self.assertEqual(self.associate(source=other, target=self.source).status_code, 400)

    def test_shared_action_evidence_visible_without_exposing_original_attachments_or_edit_rights(self):
        self.assertEqual(self.associate().status_code, 200)
        action_id = self.create_action()
        private = AnomalyAttachment.objects.create(anomaly=self.root,
                    file=SimpleUploadedFile("original.txt", b"original privado"), original_name="original.txt", uploaded_by=self.admin)
        shared = AnomalyAttachment.objects.create(anomaly=self.root, observation_action_id=action_id,
                    file=SimpleUploadedFile("accion.txt", b"resultado comun"), original_name="accion.txt", uploaded_by=self.admin, note="Evidencia comun")
        self.client.force_authenticate(self.reporter)
        # Only the source is visible to this reporter.
        self.root.reporter = self.admin
        self.root.save()
        response = self.client.get(f"/api/v1/anomalies/{self.source.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["observation_actions"]), 1)
        self.assertEqual([item["id"] for item in response.data["attachments"]], [str(shared.pk)])
        self.assertEqual(self.client.get(f"/api/v1/anomalies/{self.root.pk}/").status_code, 404)
        shared_url = response.data["attachments"][0]["file_url"]
        download = self.client.get(shared_url)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"resultado comun")
        private_url = reverse("api:anomalies:attachment-download", kwargs={"attachment_id": private.pk})
        self.assertEqual(self.client.get(private_url).status_code, 404)

    def test_multiple_findings_share_one_action_and_are_searchable(self):
        other = self.make_anomaly("SECOND")
        self.assertEqual(self.associate().status_code, 200)
        self.assertEqual(self.associate(source=other).status_code, 200)
        self.create_action()
        response = self.client.get("/api/v1/anomalies/immediate-actions/", {"search": "SECOND"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(len(response.data["results"][0]["observation_anomalies"]), 2)
        self.client.force_authenticate(self.manager)
        received = self.client.get("/api/v1/anomalies/", {"relationship": "received"})
        self.assertEqual(received.data["count"], 3)
        action_list = self.client.get("/api/v1/actions/work-items/", {"anomaly": str(other.pk)})
        self.assertEqual(action_list.status_code, 200)
        self.assertEqual(action_list.data["count"], 1)

    def test_classification_cannot_be_changed_while_group_is_linked(self):
        self.assertEqual(self.associate().status_code, 200)
        for anomaly in (self.root, self.source):
            response = self.client.patch(f"/api/v1/anomalies/{anomaly.pk}/", {
                "severity": str(self.nc.pk), "classification_responsible": str(self.manager.pk),
                "treatment_deadline": timezone.localdate().isoformat(),
            }, format="json")
            self.assertEqual(response.status_code, 400)

    def test_previous_task_becomes_ineligible_and_detach_requires_reason_and_preserves_history(self):
        self.source.owner = self.manager
        self.source.severity = self.obs
        self.source.save()
        AnomalyImmediateAction.objects.create(anomaly=self.source, responsible=self.manager,
                                               action_date=timezone.localdate() - timedelta(days=2), observation="")
        notify_finding_management_assigned(anomaly=self.source, responsible=self.manager, actor=self.admin)
        recipient = NotificationRecipient.objects.filter(notification__source_id=self.source.pk).first()
        self.assertIsNotNone(current_due_date(recipient))
        self.assertEqual(self.associate().status_code, 200)
        recipient.refresh_from_db()
        self.assertIsNone(current_due_date(recipient))
        url = f"/api/v1/anomalies/{self.source.pk}/detach-observation/"
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)
        self.client.force_authenticate(self.manager)
        payload = {"reason": "Requiere una solucion diferente", "observation_due_date": timezone.localdate().isoformat()}
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.observation_parent_id)
        self.assertEqual(self.source.current_status, "in_evaluation")
        self.assertTrue(self.source.status_history.filter(comment__contains="ADMIN separa").exists())
        self.assertEqual(self.root.associated_observation_anomalies.count(), 0)


@skipUnless(connection.vendor == "postgresql", "La concurrencia requiere bloqueos reales de PostgreSQL.")
class ObservationAssociationConcurrencyTests(APITransactionTestCase):
    # PostgreSQL must cascade the test-only flush to legacy unmanaged role-scope tables.
    available_apps = [config.name for config in apps.get_app_configs()]
    # The same fixtures are committed, so separate connections can exercise the locks.
    setUp = ObservationAssociationTests.setUp
    make_anomaly = ObservationAssociationTests.make_anomaly

    def run_concurrently(self, pairs):
        barrier = Barrier(2)

        def associate(pair):
            client = APIClient()
            client.force_authenticate(self.admin)
            barrier.wait(timeout=10)
            try:
                response = client.post(f"/api/v1/anomalies/{pair[0]}/associate-observation/", {
                    "observation": str(pair[1]), "reason": "Cobertura conjunta confirmada",
                }, format="json")
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return sorted(executor.map(associate, pairs))

    def test_two_requests_cannot_duplicate_the_same_association(self):
        statuses = self.run_concurrently([(self.source.pk, self.root.pk)] * 2)
        self.assertEqual(statuses, [200, 400])
        self.assertEqual(self.root.associated_observation_anomalies.count(), 1)
        self.assertEqual(Notification.objects.filter(template_code="observation_anomaly_associated").count(), 1)

    def test_cross_associations_cannot_create_a_cycle(self):
        AnomalyImmediateAction.objects.filter(anomaly=self.root).update(observation="")
        second = self.make_anomaly("SECOND-OBS", severity=self.obs, owner=self.manager,
                                    current_stage=AnomalyStage.CLASSIFICATION, current_status=AnomalyStatus.IN_EVALUATION,
                                    observation_resolution_path=ObservationResolutionPath.OBSERVATION)
        AnomalyImmediateAction.objects.create(anomaly=second, responsible=self.manager,
                                               action_date=timezone.localdate(), observation="")
        statuses = self.run_concurrently([(self.root.pk, second.pk), (second.pk, self.root.pk)])
        self.assertEqual(statuses, [200, 400])
        self.root.refresh_from_db()
        second.refresh_from_db()
        self.assertNotEqual(bool(self.root.observation_parent_id), bool(second.observation_parent_id))
