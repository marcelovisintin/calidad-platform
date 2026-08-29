from datetime import date, datetime
from tempfile import TemporaryDirectory

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.actions.models import (
    ActionItem,
    ActionItemStatus,
    ActionPlan,
    Treatment,
    TreatmentEffectivenessValidationResult,
    TreatmentLearnedLesson,
    TreatmentStatus,
    TreatmentTask,
    TreatmentTaskStatus,
)
from apps.anomalies.models import (
    AffectedOrder,
    Anomaly,
    AnomalyClassification,
    AnomalyImmediateAction,
    AnomalyStage,
    AnomalyStatus,
    ObservationResolutionPath,
)
from apps.catalog.models import ActionType, AnomalyOrigin, AnomalyType, Area, OrderType, Priority, Severity, Site
from apps.indicators.models import IndicatorReport, IndicatorReportStatus
from apps.notifications.models import NotificationChannel
from apps.notifications.services.email_delivery import dispatch_pending_email_notifications


class IndicatorsApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="indicator_admin",
            email="indicator-admin@example.com",
            password="Test-password-2026!",
            access_level=User.AccessLevel.ADMINISTRADOR,
        )
        self.developer = User.objects.create_user(
            username="indicator_developer",
            email="indicator-developer@example.com",
            password="Test-password-2026!",
            access_level=User.AccessLevel.DESARROLLADOR,
        )
        self.operator = User.objects.create_user(
            username="indicator_operator",
            email="indicator-operator@example.com",
            password="Test-password-2026!",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
        )
        self.site = Site.objects.create(code="S1", name="Planta", display_order=1)
        self.area_one = Area.objects.create(site=self.site, code="001", name="Corte", display_order=1)
        self.area_two = Area.objects.create(site=self.site, code="002", name="Armado", display_order=2)
        self.anomaly_type = AnomalyType.objects.create(code="T1", name="Desvio", display_order=1)
        self.origin = AnomalyOrigin.objects.create(code="O1", name="Interna", display_order=1)
        self.priority = Priority.objects.create(code="P1", name="Normal", display_order=1)
        self.action_type, _ = ActionType.objects.get_or_create(
            code="IND_AC",
            defaults={"name": "Correctiva indicador", "display_order": 901},
        )
        self.order_type, _ = OrderType.objects.get_or_create(
            code="IND_OP",
            defaults={"name": "Orden prueba indicador", "display_order": 901},
        )
        self.non_invalid_severity = Severity.objects.create(code="NC", name="No conformidad", display_order=1)
        self.invalid_severity = Severity.objects.create(
            code="INV",
            name="Invalida",
            display_order=2,
            closes_anomaly_as_invalid=True,
            requires_classification_responsible=False,
        )

    def _date_time(self, value: str):
        return timezone.make_aware(datetime.fromisoformat(f"{value}T10:00:00"))

    def _anomaly(self, code: str, detected: str, *, area=None, status=AnomalyStatus.REGISTERED, severity=None, closed=None):
        stage = AnomalyStage.CLOSURE if status == AnomalyStatus.CLOSED else AnomalyStage.REGISTRATION
        return Anomaly.objects.create(
            code=code,
            title=f"Anomalia {code}",
            description="Caso para indicador",
            current_status=status,
            current_stage=stage,
            site=self.site,
            area=area or self.area_one,
            reporter=self.admin,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.origin,
            severity=severity,
            priority=self.priority,
            detected_at=self._date_time(detected),
            closed_at=self._date_time(closed) if closed else None,
        )

    def test_admin_can_list_the_nine_indicator_dashboards(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/v1/indicators/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["indicators"]), 9)
        self.assertEqual(response.data["indicators"][0]["key"], "anomalies-treated")
        self.assertEqual(response.data["indicators"][-1]["key"], "learned-lessons")

    def test_developer_can_list_indicators(self):
        self.client.force_authenticate(self.developer)

        response = self.client.get("/api/v1/indicators/")

        self.assertEqual(response.status_code, 200)

    def test_operator_cannot_view_global_indicators(self):
        self.client.force_authenticate(self.operator)

        response = self.client.get("/api/v1/indicators/")

        self.assertEqual(response.status_code, 403)

    def test_anomalies_treated_dashboard_calculates_flow_and_cohort(self):
        self._anomaly(
            "A-1",
            "2026-01-10",
            status=AnomalyStatus.CLOSED,
            severity=self.non_invalid_severity,
            closed="2026-02-10",
        )
        self._anomaly("A-2", "2026-03-10", severity=self.non_invalid_severity)
        self._anomaly(
            "A-3",
            "2026-04-10",
            status=AnomalyStatus.CLOSED,
            severity=self.invalid_severity,
            closed="2026-04-11",
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/anomalies-treated/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )

        self.assertEqual(response.status_code, 200)
        metrics = {item["key"]: item for item in response.data["metrics"]}
        self.assertEqual(metrics["generated"]["value"], 3)
        self.assertEqual(metrics["treated"]["value"], 1)
        self.assertEqual(metrics["treated"]["percentage"], 33.3)
        self.assertEqual(metrics["cohort"]["value"], 1)
        self.assertEqual(metrics["pending"]["value"], 1)
        breakdown = {item["key"]: item["count"] for item in response.data["breakdown"]}
        self.assertEqual(breakdown["invalid"], 1)

    def test_treatments_dashboard_uses_effective_validation_as_completion_date(self):
        anomaly = self._anomaly("TRT-A", "2026-01-05", severity=self.non_invalid_severity)
        completed = Treatment.objects.create(
            code="TRT-2026-0001",
            primary_anomaly=anomaly,
            responsible=self.admin,
            status=TreatmentStatus.COMPLETED,
            effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
            effectiveness_validated_at=self._date_time("2026-02-10"),
        )
        Treatment.objects.filter(pk=completed.pk).update(created_at=self._date_time("2026-01-15"))
        opened = Treatment.objects.create(
            code="TRT-2026-0002",
            primary_anomaly=anomaly,
            responsible=self.admin,
            status=TreatmentStatus.IN_PROGRESS,
        )
        Treatment.objects.filter(pk=opened.pk).update(created_at=self._date_time("2026-03-15"))
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/treatments/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )

        self.assertEqual(response.status_code, 200)
        metrics = {item["key"]: item for item in response.data["metrics"]}
        self.assertEqual(metrics["created"]["value"], 2)
        self.assertEqual(metrics["completed"]["value"], 1)
        self.assertEqual(metrics["completed"]["percentage"], 50.0)
        self.assertEqual(metrics["open"]["value"], 1)

    def test_anomalies_by_process_returns_quantity_and_percentage(self):
        self._anomaly("P-1", "2026-01-05", area=self.area_one)
        self._anomaly("P-2", "2026-02-05", area=self.area_one)
        self._anomaly("P-3", "2026-02-06", area=self.area_two)
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/anomalies-by-process/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"][0]["value"], 3)
        self.assertEqual(response.data["breakdown"][0]["count"], 2)
        self.assertEqual(response.data["breakdown"][0]["percentage"], 66.7)
        self.assertEqual(response.data["rows"]["count"], 2)
        february = next(item for item in response.data["series"] if item["period"] == "2026-02-01")
        self.assertEqual(sorted(item["percentage"] for item in february["values"]), [50.0, 50.0])

        filtered = self.client.get(
            "/api/v1/indicators/anomalies-by-process/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "area": self.area_one.pk},
        )
        self.assertEqual(filtered.data["metrics"][0]["value"], 2)
        self.assertEqual(len(filtered.data["breakdown"]), 1)

    def test_dashboard_rejects_invalid_period(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/anomalies-treated/",
            {"date_from": "2026-12-31", "date_to": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 400)

    def test_classification_and_pareto_use_structured_catalogs(self):
        first = self._anomaly("C-1", "2026-01-10", severity=self.non_invalid_severity)
        second = self._anomaly("C-2", "2026-02-10", severity=self.non_invalid_severity)
        first.observation_resolution_path = ObservationResolutionPath.TREATMENT_PENDING
        first.save(update_fields=["observation_resolution_path"])
        for anomaly, classified in ((first, "2026-01-11"), (second, "2026-02-11")):
            AnomalyClassification.objects.create(
                anomaly=anomaly,
                classified_by=self.admin,
                classified_at=self._date_time(classified),
            )
        self.client.force_authenticate(self.admin)

        classification = self.client.get(
            "/api/v1/indicators/finding-classification/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )
        pareto = self.client.get(
            "/api/v1/indicators/repetition-pareto/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "group_by": "process_type"},
        )

        self.assertEqual(classification.status_code, 200)
        self.assertEqual(classification.data["metrics"][0]["value"], 2)
        self.assertEqual({item["label"] for item in classification.data["breakdown"]}, {"No conformidad", "Observacion TRT"})
        self.assertEqual(pareto.status_code, 200)
        self.assertEqual(pareto.data["breakdown"][0]["count"], 2)
        self.assertEqual(pareto.data["breakdown"][0]["cumulative_percentage"], 100.0)

    def test_actions_integrate_direct_and_treatment_actions(self):
        anomaly = self._anomaly("AC-1", "2026-01-10", severity=self.non_invalid_severity)
        plan = ActionPlan.objects.create(anomaly=anomaly, owner=self.admin)
        direct = ActionItem.objects.create(
            action_plan=plan,
            action_type=self.action_type,
            assigned_to=self.admin,
            title="Accion directa",
            status=ActionItemStatus.COMPLETED,
            due_date=date(2026, 2, 20),
            completed_at=self._date_time("2026-02-15"),
        )
        ActionItem.objects.filter(pk=direct.pk).update(created_at=self._date_time("2026-02-01"))
        treatment = Treatment.objects.create(code="TRT-AC-1", primary_anomaly=anomaly, responsible=self.admin)
        task = TreatmentTask.objects.create(
            treatment=treatment,
            title="Accion tratamiento",
            responsible=self.admin,
            status=TreatmentTaskStatus.PENDING,
            execution_date=date(2026, 1, 20),
        )
        TreatmentTask.objects.filter(pk=task.pk).update(created_at=self._date_time("2026-02-02"))
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/actions/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )

        self.assertEqual(response.status_code, 200)
        metrics = {item["key"]: item for item in response.data["metrics"]}
        self.assertEqual(metrics["total"]["value"], 2)
        self.assertEqual(metrics["overdue"]["value"], 1)
        self.assertEqual(metrics["on_time"]["percentage"], 100.0)

    def test_effectiveness_and_lessons_keep_treatment_and_observation_paths(self):
        anomaly = self._anomaly("EF-1", "2026-01-10", severity=self.non_invalid_severity)
        treatment = Treatment.objects.create(
            code="TRT-EF-1",
            primary_anomaly=anomaly,
            responsible=self.admin,
            status=TreatmentStatus.COMPLETED,
            effectiveness_evaluation_date=date(2026, 2, 10),
            effectiveness_responsible=self.admin,
            effectiveness_validation_result=TreatmentEffectivenessValidationResult.EFFECTIVE,
            effectiveness_validated_at=self._date_time("2026-02-10"),
        )
        TreatmentLearnedLesson.objects.create(
            treatment=treatment,
            has_learning=True,
            learned_text="Actualizar instruccion",
            procedure_modified=True,
            saved_by=self.admin,
            saved_at=self._date_time("2026-02-11"),
        )
        observation = self._anomaly("EF-2", "2026-01-12", severity=self.non_invalid_severity)
        AnomalyImmediateAction.objects.create(
            anomaly=observation,
            responsible=self.admin,
            action_date=date(2026, 1, 15),
            effectiveness_due_at=date(2026, 2, 15),
            effectiveness_verified_at=self._date_time("2026-02-15"),
            effectiveness_is_effective=False,
            observation="Observacion controlada",
        )
        self.client.force_authenticate(self.admin)

        effectiveness = self.client.get(
            "/api/v1/indicators/effectiveness/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )
        lessons = self.client.get(
            "/api/v1/indicators/learned-lessons/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )

        self.assertEqual(effectiveness.status_code, 200)
        metrics = {item["key"]: item for item in effectiveness.data["metrics"]}
        self.assertEqual(metrics["performed"]["value"], 2)
        self.assertEqual(metrics["effective"]["percentage"], 50.0)
        self.assertEqual(lessons.status_code, 200)
        lesson_metrics = {item["key"]: item for item in lessons.data["metrics"]}
        self.assertEqual(lesson_metrics["coverage"]["percentage"], 100.0)
        self.assertEqual(lesson_metrics["modified"]["percentage"], 100.0)

    def test_affected_orders_distinguish_unique_orders_records_and_quantity(self):
        first = self._anomaly("OR-1", "2026-03-10", severity=self.non_invalid_severity)
        second = self._anomaly("OR-2", "2026-03-11", severity=self.non_invalid_severity)
        AffectedOrder.objects.create(anomaly=first, order_type=self.order_type, number="100", quantity=5)
        AffectedOrder.objects.create(anomaly=second, order_type=self.order_type, number="100", quantity=3)
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/affected-orders/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )

        self.assertEqual(response.status_code, 200)
        metrics = {item["key"]: item for item in response.data["metrics"]}
        self.assertEqual(metrics["unique"]["value"], 1)
        self.assertEqual(metrics["records"]["value"], 2)
        self.assertEqual(metrics["quantity"]["value"], 8)

    def test_csv_exports_all_filtered_rows_with_semicolon_and_bom(self):
        self._anomaly("CSV-1", "2026-01-10", severity=self.non_invalid_severity)
        self._anomaly("CSV-2", "2026-01-11", severity=self.non_invalid_severity)
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            "/api/v1/indicators/anomalies-treated/csv/",
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "page_size": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        content = response.content.decode("utf-8-sig")
        self.assertIn("Codigo;Titulo;Proceso", content)
        self.assertIn("CSV-1", content)
        self.assertIn("CSV-2", content)

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_pdf_report_is_audited_attached_and_removed_after_delivery(self):
        self._anomaly("PDF-1", "2026-01-10", severity=self.non_invalid_severity)
        self.admin.email_notifications_enabled = True
        self.admin.save(update_fields=["email_notifications_enabled", "updated_at"])
        self.client.force_authenticate(self.admin)

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                "/api/v1/indicators/anomalies-treated/reports/",
                {
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                    "recipient_ids": [str(self.admin.pk)],
                },
                format="json",
            )

            self.assertEqual(response.status_code, 201)
            report = IndicatorReport.objects.get(pk=response.data["id"])
            self.assertEqual(report.status, IndicatorReportStatus.QUEUED)
            self.assertEqual(len(report.checksum_sha256), 64)
            self.assertEqual(report.report_file.read(5), b"%PDF-")
            self.assertEqual(report.notification.recipients.filter(channel=NotificationChannel.EMAIL).count(), 1)

            dispatch = dispatch_pending_email_notifications()
            report.refresh_from_db()
            self.assertEqual(dispatch["delivered"], 1)
            self.assertEqual(report.status, IndicatorReportStatus.COMPLETED)
            self.assertFalse(report.report_file)
            self.assertIsNone(report.expires_at)
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].attachments[0][0], report.original_name)

    @override_settings(
        EMAIL_NOTIFICATIONS_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_report_sends_automatic_copy_to_eligible_creator_without_duplicates(self):
        self._anomaly("PDF-COPY", "2026-01-10", severity=self.non_invalid_severity)
        User.objects.filter(pk__in=[self.admin.pk, self.developer.pk]).update(email_notifications_enabled=True)
        self.client.force_authenticate(self.admin)

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                "/api/v1/indicators/anomalies-treated/reports/",
                {
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                    "recipient_ids": [str(self.developer.pk)],
                },
                format="json",
            )

            self.assertEqual(response.status_code, 201)
            report = IndicatorReport.objects.get(pk=response.data["id"])
            destinations = set(report.notification.recipients.values_list("destination", flat=True))
            self.assertEqual(destinations, {self.admin.email, self.developer.email})

            dispatch = dispatch_pending_email_notifications()
            report.refresh_from_db()
            self.assertEqual(dispatch["delivered"], 2)
            self.assertEqual(len(mail.outbox), 2)
            self.assertFalse(report.report_file)
