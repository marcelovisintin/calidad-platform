from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.constants import PERMISSION_CLASSIFY_ANOMALY, PERMISSION_EDIT_ANOMALY
from apps.accounts.models import User
from apps.accounts.services.role_setup import ensure_required_permissions
from apps.actions.models import Treatment, TreatmentAnomaly, TreatmentParticipant
from apps.audit.models import AuditEvent
from apps.anomalies.models import (
    AffectedOrder,
    Anomaly,
    AnomalyClassification,
    AnomalyEffectivenessCheck,
    AnomalyCodeReservation,
    AnomalyImmediateAction,
    AnomalyInitialVerification,
    AnomalyParticipant,
    AnomalyStage,
    AnomalyStatus,
    ObservationResolutionPath,
    ObservationAction,
    ParticipantRole,
)
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, OrderType, Priority, Severity, Site
from apps.notifications.models import (
    DeliveryStatus,
    Notification,
    NotificationChannel,
    NotificationRecipient,
    NotificationTaskType,
    RecipientTaskStatus,
)


class AnomalyCreateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=self.user)

        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.severity_alt = Severity.objects.create(code="MEDIA", name="Media")
        self.severity_extra = Severity.objects.create(code="BAJA", name="Baja")
        self.severity_observation = Severity.objects.create(code="OBSERVACION", name="Observacion")
        self.severity_invalid = Severity.objects.create(
            code="INVALIDA",
            name="Invalida",
            requires_classification_responsible=False,
            closes_anomaly_as_invalid=True,
        )
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

    def _classification_payload(self, severity):
        payload = {"severity": str(severity.pk), "classification_responsible": str(self.user.pk)}
        if severity.code == "NC":
            payload["treatment_deadline"] = (timezone.localdate() + timedelta(days=30)).isoformat()
        if severity.pk == self.severity_observation.pk:
            payload.update(
                {
                    "observation_due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
                    "observation_comment": "Observacion confirmada desde Revision de hallazgos.",
                }
            )
        return payload

    def _build_payload(self, suffix: str, *, include_severity: bool = True):
        payload = {
            "title": f"Desviacion de prueba {suffix}",
            "description": "Descripcion",
            "site": str(self.site.pk),
            "area": str(self.area.pk),
            "anomaly_type": str(self.anomaly_type.pk),
            "anomaly_origin": str(self.anomaly_origin.pk),
            "priority": str(self.priority.pk),
            "detected_at": timezone.now().isoformat(),
            "manufacturing_order_number": f"OF-{suffix}",
            "affected_quantity": 12,
            "affected_process": "Inspeccion final",
            "registration_comment": "Registro inicial desde test.",
        }
        if include_severity:
            payload["severity"] = str(self.severity.pk)
        return payload

    def _immediate_anomaly(self, code="AI-001"):
        anomaly = Anomaly.objects.create(
            code=code,
            title=f"Observacion {code}",
            description="Caso de Observacion",
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity,
            priority=self.priority,
            detected_at=timezone.now(),
            classification_summary="Observacion",
            current_stage=AnomalyStage.CLASSIFICATION,
            current_status=AnomalyStatus.IN_EVALUATION,
            created_by=self.user,
        )
        AnomalyInitialVerification.objects.create(
            anomaly=anomaly,
            verified_by=self.user,
            verified_at=timezone.now(),
            summary="Verificacion inicial registrada.",
            created_by=self.user,
            updated_by=self.user,
        )
        AnomalyClassification.objects.create(
            anomaly=anomaly,
            classified_by=self.user,
            classified_at=timezone.now(),
            requires_action_plan=True,
            requires_effectiveness_verification=True,
            summary="Observacion",
            created_by=self.user,
            updated_by=self.user,
        )
        return anomaly

    def test_create_anomaly_returns_confirmation_payload(self):
        payload = self._build_payload("001")

        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("detected_at", response.data)
        self.assertIn("current_responsible", response.data)
        self.assertEqual(response.data["current_status"], AnomalyStatus.REGISTERED)
        self.assertEqual(response.data["current_stage"], AnomalyStage.REGISTRATION)
        self.assertIsNone(response.data["current_responsible"])
        self.assertEqual(response.data["manufacturing_order_number"], "OF-001")
        self.assertEqual(response.data["affected_quantity"], 12)
        self.assertEqual(len(response.data["affected_orders"]), 1)
        self.assertEqual(response.data["affected_orders"][0]["order_type"]["code"], "OF")
        self.assertEqual(response.data["affected_orders"][0]["number"], "OF-001")
        self.assertRegex(response.data["code"], rf"^{timezone.localdate().year}\d{{4}}$")

    def test_update_anomaly_with_area_from_another_site_returns_controlled_error(self):
        create_response = self.client.post("/api/v1/anomalies/", self._build_payload("AREA"), format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        other_site = Site.objects.create(code="S02", name="Sitio 2")
        other_area = Area.objects.create(site=other_site, code="A02", name="Area 2")

        response = self.client.patch(
            f"/api/v1/anomalies/{create_response.data['id']}/",
            {"area": str(other_area.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("area", response.data)
        self.assertIn("no pertenece al sitio", str(response.data["area"][0]))
        anomaly = Anomaly.objects.get(pk=create_response.data["id"])
        self.assertEqual(anomaly.area_id, self.area.pk)

    def test_create_anomaly_accepts_multiple_affected_orders(self):
        payload = self._build_payload("MULTI")
        payload.pop("manufacturing_order_number")
        payload.pop("affected_quantity")
        op = OrderType.objects.get(code="OP")
        om = OrderType.objects.get(code="OM")
        payload["affected_orders"] = [
            {"order_type": str(op.pk), "number": "1001", "quantity": 12},
            {"order_type": str(om.pk), "number": "M-44", "quantity": 2},
        ]

        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["affected_orders"]), 2)
        self.assertEqual(
            {(item["order_type"]["code"], item["number"], item["quantity"]) for item in response.data["affected_orders"]},
            {("OP", "1001", 12), ("OM", "M-44", 2)},
        )
        self.assertEqual(AffectedOrder.objects.filter(anomaly_id=response.data["id"]).count(), 2)

    def test_create_anomaly_rejects_duplicate_affected_order(self):
        payload = self._build_payload("DUP")
        order_type = OrderType.objects.get(code="OP")
        payload["affected_orders"] = [
            {"order_type": str(order_type.pk), "number": "ABC-1", "quantity": 5},
            {"order_type": str(order_type.pk), "number": "abc-1", "quantity": 7},
        ]

        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("affected_orders", response.data)

    def test_affected_orders_panel_filters_and_totalizes_all_filtered_rows(self):
        payload = self._build_payload("PANEL")
        op = OrderType.objects.get(code="OP")
        of = OrderType.objects.get(code="OF")
        payload["affected_orders"] = [
            {"order_type": str(op.pk), "number": "OP-200", "quantity": 10},
            {"order_type": str(of.pk), "number": "OF-300", "quantity": 4},
        ]
        created = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/anomalies/affected-orders/",
            {"order_type": str(op.pk), "quantity_min": "5"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["number"], "OP-200")
        self.assertEqual(response.data["totals"]["records"], 1)
        self.assertEqual(response.data["totals"]["unique_orders"], 1)
        self.assertEqual(response.data["totals"]["anomalies"], 1)
        self.assertEqual(response.data["totals"]["total_quantity"], 10)

    def test_affected_orders_panel_exports_csv(self):
        created = self.client.post("/api/v1/anomalies/", self._build_payload("CSV"), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        response = self.client.get("/api/v1/anomalies/affected-orders/", {"export": "csv"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = response.content.decode("utf-8-sig")
        self.assertIn("Tipo;Numero;Cantidad;Anomalia", content)
        self.assertIn("OF;OF-CSV;12", content)

    def test_affected_orders_panel_respects_anomaly_visibility(self):
        admin_created = self.client.post("/api/v1/anomalies/", self._build_payload("ADMIN"), format="json")
        self.assertEqual(admin_created.status_code, status.HTTP_201_CREATED)

        operator = User.objects.create_user(
            username="order_operator",
            email="order_operator@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        own_anomaly = Anomaly.objects.create(
            code="OWN-ORDER-1",
            title="Anomalia visible del operador",
            description="Caso propio",
            site=self.site,
            area=self.area,
            reporter=operator,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=operator,
            updated_by=operator,
        )
        AffectedOrder.objects.create(
            anomaly=own_anomaly,
            order_type=OrderType.objects.get(code="OP"),
            number="OWN-100",
            quantity=3,
            created_by=operator,
            updated_by=operator,
        )
        self.client.force_authenticate(user=operator)

        response = self.client.get("/api/v1/anomalies/affected-orders/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["number"], "OWN-100")
        self.assertEqual(response.data["totals"]["anomalies"], 1)

    def test_create_anomaly_does_not_require_affected_process(self):
        payload = self._build_payload("010")
        payload.pop("affected_process")

        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["affected_process"], "")

    def test_create_anomaly_generates_consecutive_visible_codes(self):
        first = self.client.post("/api/v1/anomalies/", self._build_payload("001"), format="json")
        second = self.client.post("/api/v1/anomalies/", self._build_payload("002"), format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

        year_prefix = str(timezone.localdate().year)
        self.assertTrue(first.data["code"].startswith(year_prefix))
        self.assertTrue(second.data["code"].startswith(year_prefix))
        self.assertEqual(int(second.data["code"][-4:]), int(first.data["code"][-4:]) + 1)
        self.assertNotEqual(first.data["id"], second.data["id"])
        self.assertFalse(
            AnomalyCodeReservation.objects.filter(anomaly__isnull=True, consumed_at__isnull=True).exists()
        )
        self.assertEqual(
            AnomalyCodeReservation.objects.filter(anomaly__isnull=False, consumed_at__isnull=False).count(),
            2,
        )


    def test_reserve_code_returns_current_year_format(self):
        response = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertRegex(response.data["code"], rf"^{timezone.localdate().year}\d{{4}}$")

        second = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data["id"], response.data["id"])

    def test_reserve_code_assigns_distinct_codes_to_distinct_users(self):
        first_user = User.objects.create_user(
            username="operario_reserva_1",
            email="operario_reserva_1@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        second_user = User.objects.create_user(
            username="operario_reserva_2",
            email="operario_reserva_2@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )

        self.client.force_authenticate(user=first_user)
        first = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")
        self.client.force_authenticate(user=second_user)
        second = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(first.data["id"], second.data["id"])
        self.assertNotEqual(first.data["code"], second.data["code"])

    @override_settings(ANOMALY_CODE_RESERVATION_MINUTES=30)
    def test_expired_unconsumed_reservation_is_released_and_reused(self):
        first_user = User.objects.create_user(
            username="operario_reserva_vencida_1",
            email="operario_reserva_vencida_1@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        second_user = User.objects.create_user(
            username="operario_reserva_vencida_2",
            email="operario_reserva_vencida_2@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )

        self.client.force_authenticate(user=first_user)
        first = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        AnomalyCodeReservation.objects.filter(pk=first.data["id"]).update(
            created_at=timezone.now() - timedelta(minutes=31)
        )

        self.client.force_authenticate(user=second_user)
        second = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")

        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data["code"], first.data["code"])
        self.assertNotEqual(second.data["id"], first.data["id"])
        self.assertFalse(AnomalyCodeReservation.objects.filter(pk=first.data["id"]).exists())

    def test_create_anomaly_consumes_reserved_code(self):
        reserve_response = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")
        self.assertEqual(reserve_response.status_code, status.HTTP_201_CREATED)

        payload = self._build_payload("006")
        payload["code_reservation_id"] = reserve_response.data["id"]

        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["code"], reserve_response.data["code"])

        reservation = AnomalyCodeReservation.objects.get(pk=reserve_response.data["id"])
        self.assertEqual(str(reservation.anomaly_id), create_response.data["id"])
        self.assertIsNotNone(reservation.consumed_at)

    def test_reserve_code_continues_after_consumed_observation_code(self):
        first_reservation = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")
        self.assertEqual(first_reservation.status_code, status.HTTP_201_CREATED)

        payload = self._build_payload("OBS-RESERVA")
        payload["code_reservation_id"] = first_reservation.data["id"]
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        classification_response = self.client.patch(
            f"/api/v1/anomalies/{create_response.data['id']}/",
            self._classification_payload(self.severity_observation),
            format="json",
        )
        self.assertEqual(classification_response.status_code, status.HTTP_200_OK)
        self.assertEqual(classification_response.data["code"], f"{first_reservation.data['code']}-OBS")

        second_reservation = self.client.post("/api/v1/anomalies/reserve-code/", {}, format="json")
        self.assertEqual(second_reservation.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            second_reservation.data["sequence"],
            first_reservation.data["sequence"] + 1,
        )

    def test_observation_classification_creates_normal_observation(self):
        create_response = self.client.post(
            "/api/v1/anomalies/",
            self._build_payload("OBS-NORMAL", include_severity=False),
            format="json",
        )
        due_date = timezone.localdate() + timedelta(days=5)

        response = self.client.patch(
            f"/api/v1/anomalies/{create_response.data['id']}/",
            {
                "severity": str(self.severity_observation.pk),
                "classification_responsible": str(self.user.pk),
                "observation_due_date": due_date.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["observation_resolution_path"], ObservationResolutionPath.OBSERVATION)
        self.assertEqual(response.data["immediate_action"]["action_date"], due_date.isoformat())
        self.assertEqual(response.data["immediate_action"]["observation"], "")
        self.assertFalse(Treatment.objects.filter(anomaly_links__anomaly_id=create_response.data["id"]).exists())

        missing_cause_response = self.client.post(
            f"/api/v1/anomalies/{create_response.data['id']}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": due_date.isoformat(),
            },
            format="json",
        )
        self.assertEqual(missing_cause_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("observation", missing_cause_response.data)

    def test_assigned_manager_decides_observation_trt_from_observation_flow(self):
        manager = User.objects.create_user(
            username="observation-manager",
            email="observation-manager@example.com",
            password="secret123",
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        create_response = self.client.post(
            "/api/v1/anomalies/",
            self._build_payload("OBS-TRT", include_severity=False),
            format="json",
        )
        due_date = timezone.localdate() + timedelta(days=7)

        response = self.client.patch(
            f"/api/v1/anomalies/{create_response.data['id']}/",
            {
                "severity": str(self.severity_observation.pk),
                "classification_responsible": str(manager.pk),
                "observation_due_date": due_date.isoformat(),
                "observation_comment": "Requiere tratamiento desde clasificacion.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["observation_resolution_path"], ObservationResolutionPath.OBSERVATION)
        self.assertEqual(response.data["immediate_action"]["responsible"]["id"], str(manager.pk))
        self.assertFalse(Treatment.objects.filter(anomaly_links__anomaly_id=create_response.data["id"]).exists())

        self.client.force_authenticate(user=manager)
        trt_response = self.client.post(
            f"/api/v1/anomalies/{create_response.data['id']}/observation/load/",
            {
                "responsible": str(manager.pk),
                "action_date": due_date.isoformat(),
                "observation": "Requiere tratamiento desde clasificacion.",
                "requires_treatment": True,
            },
            format="json",
        )

        self.assertEqual(trt_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            trt_response.data["observation_resolution_path"],
            ObservationResolutionPath.TREATMENT,
        )
        treatment = Treatment.objects.get(primary_anomaly_id=create_response.data["id"])
        self.assertEqual(treatment.responsible_id, manager.pk)
        self.assertEqual(treatment.created_by_id, manager.pk)
        self.assertFalse(AnomalyParticipant.objects.filter(
            anomaly_id=create_response.data["id"], user=manager, role=ParticipantRole.VERIFIER,
        ).exists())
        self.assertTrue(AnomalyParticipant.objects.filter(
            anomaly_id=create_response.data["id"], user=self.user, role=ParticipantRole.VERIFIER,
        ).exists())
        detail = self.client.get(f"/api/v1/anomalies/{create_response.data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["treatments"][0]["id"], str(treatment.pk))
        self.assertEqual(detail.data["treatments"][0]["participants"][0]["user"]["id"], str(manager.pk))
        self.assertEqual(detail.data["treatments"][0]["participants"][0]["role"], "owner")

    def test_create_anomaly_allows_missing_severity(self):
        payload = self._build_payload("003", include_severity=False)

        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["severity"])

    def test_immediate_action_load_keeps_anomaly_pending_verification(self):
        anomaly = self._immediate_anomaly()

        response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/immediate-action/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Observacion inicial",
                "actions_taken": "Acciones tomadas",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], AnomalyStatus.PENDING_VERIFICATION)
        self.assertEqual(response.data["current_stage"], AnomalyStage.EFFECTIVENESS_VERIFICATION)
        self.assertEqual(response.data["observation_resolution_path"], ObservationResolutionPath.OBSERVATION)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.observation_resolution_path, ObservationResolutionPath.OBSERVATION)
        immediate_action = AnomalyImmediateAction.objects.get(anomaly=anomaly)
        self.assertIsNone(immediate_action.effectiveness_verified_at)
        self.assertIsNone(immediate_action.effectiveness_is_effective)
        history_entries = response.data["status_history"]
        self.assertTrue(any("Acciones tomadas" in item["evidence_note"] for item in history_entries))
        load_history = next(item for item in history_entries if "Carga de Observacion" in item["comment"])
        self.assertIn("Observacion inicial", load_history["evidence_note"])
        self.assertIn("Camino elegido: OBSERVATION", load_history["evidence_note"])

        list_response = self.client.get("/api/v1/anomalies/immediate-actions/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        anomaly_ids = {item["id"] for item in list_response.data["results"]}
        self.assertIn(str(anomaly.pk), anomaly_ids)

    def test_observation_list_includes_anomaly_classified_by_severity_only(self):
        anomaly = Anomaly.objects.create(
            code="OBS-SEV-001",
            title="Observacion por severidad",
            description="Caso clasificado desde catalogo",
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity_observation,
            priority=self.priority,
            detected_at=timezone.now(),
            classification_summary="Criterio de revision aplicado.",
            current_stage=AnomalyStage.CLASSIFICATION,
            current_status=AnomalyStatus.IN_EVALUATION,
            created_by=self.user,
            updated_by=self.user,
        )

        response = self.client.get("/api/v1/anomalies/immediate-actions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        anomaly_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(anomaly.pk), anomaly_ids)

    def test_observation_is_visible_and_manageable_only_by_assigned_responsible(self):
        responsible = User.objects.create_user(
            username="responsable_observacion",
            email="responsable_observacion@example.com",
            password="secret123",
            primary_sector=self.area,
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        other_user = User.objects.create_user(
            username="otro_observacion",
            email="otro_observacion@example.com",
            password="secret123",
            primary_sector=self.area,
        )
        assigned = self._immediate_anomaly("AI-RESP-001")
        assigned.owner = responsible
        assigned.save(update_fields=["owner", "updated_at"])
        other_assigned = self._immediate_anomaly("AI-RESP-002")
        other_assigned.owner = other_user
        other_assigned.save(update_fields=["owner", "updated_at"])

        self.client.force_authenticate(user=responsible)
        list_response = self.client.get("/api/v1/anomalies/immediate-actions/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        anomaly_ids = {item["id"] for item in list_response.data["results"]}
        self.assertIn(str(assigned.pk), anomaly_ids)
        self.assertNotIn(str(other_assigned.pk), anomaly_ids)

        load_response = self.client.post(
            f"/api/v1/anomalies/{assigned.pk}/observation/load/",
            {
                "responsible": str(responsible.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Gestionada por responsable asignado",
            },
            format="json",
        )

        self.assertEqual(load_response.status_code, status.HTTP_200_OK)
        self.assertEqual(load_response.data["immediate_action"]["responsible"]["id"], str(responsible.pk))

        evidence = SimpleUploadedFile("evidencia-responsable.txt", b"ok", content_type="text/plain")
        upload_response = self.client.post(
            f"/api/v1/anomalies/{assigned.pk}/attachments/",
            {"file": evidence, "original_name": "evidencia-responsable.txt", "content_type": "text/plain"},
            format="multipart",
        )

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=other_user)
        other_list_response = self.client.get("/api/v1/anomalies/immediate-actions/")
        other_ids = {item["id"] for item in other_list_response.data["results"]}
        self.assertNotIn(str(assigned.pk), other_ids)

    def test_immediate_action_not_effective_stays_pending(self):
        anomaly = self._immediate_anomaly("AI-002")
        base_payload = {
            "responsible": str(self.user.pk),
            "action_date": timezone.localdate().isoformat(),
            "observation": "Observacion inicial",
            "actions_taken": "Acciones tomadas",
        }
        self.client.post(f"/api/v1/anomalies/{anomaly.pk}/immediate-action/", base_payload, format="json")

        response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/immediate-action/",
            base_payload
            | {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "No eficaz reveer acciones tomadas",
                "evidences": SimpleUploadedFile("verificacion-1.txt", b"No eficaz", content_type="text/plain"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], AnomalyStatus.IN_TREATMENT)
        self.assertEqual(response.data["current_stage"], AnomalyStage.EXECUTION_AND_FOLLOW_UP)
        self.assertEqual(response.data["immediate_action"]["effectiveness_is_effective"], False)
        self.assertIn("No eficaz", response.data["effectiveness_summary"])
        self.assertEqual(len(response.data["effectiveness_checks"]), 1)
        self.assertIn("Resultado: No eficaz", response.data["status_history"][0]["evidence_note"])

        second_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/immediate-action/",
            base_payload
            | {
                "actions_taken": "Acciones corregidas",
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "Sigue no eficaz",
                "evidences": SimpleUploadedFile("verificacion-2.txt", b"Sigue no eficaz", content_type="text/plain"),
            },
            format="multipart",
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data["current_status"], AnomalyStatus.IN_TREATMENT)
        self.assertEqual(len(second_response.data["effectiveness_checks"]), 2)
        no_effective_history = [
            item for item in second_response.data["status_history"]
            if "No eficaz" in item["comment"]
        ]
        self.assertEqual(len(no_effective_history), 2)
        self.assertTrue(any("Sigue no eficaz" in item["evidence_note"] for item in no_effective_history))

    def test_immediate_action_effective_closes_anomaly(self):
        anomaly = self._immediate_anomaly("AI-003")
        payload = {
            "responsible": str(self.user.pk),
            "action_date": timezone.localdate().isoformat(),
            "observation": "Observacion inicial",
            "actions_taken": "Acciones tomadas",
            "effectiveness_verified_at": timezone.now().isoformat(),
            "effectiveness_is_effective": True,
            "effectiveness_comment": "Fue eficaz",
            "evidences": SimpleUploadedFile("verificacion.txt", b"Fue eficaz", content_type="text/plain"),
        }

        response = self.client.post(f"/api/v1/anomalies/{anomaly.pk}/immediate-action/", payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], AnomalyStatus.CLOSED)
        self.assertEqual(response.data["current_stage"], AnomalyStage.CLOSURE)
        self.assertEqual(response.data["immediate_action"]["effectiveness_is_effective"], True)

    def test_observation_flow_records_load_action_evidence_and_effectiveness(self):
        anomaly = self._immediate_anomaly("AI-004")

        load_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
                "observation": "Observacion cargada desde flujo nuevo",
            },
            format="json",
        )

        self.assertEqual(load_response.status_code, status.HTTP_200_OK)
        self.assertEqual(load_response.data["observation_resolution_path"], ObservationResolutionPath.OBSERVATION)
        self.assertFalse(AnomalyParticipant.objects.filter(
            anomaly=anomaly, user=self.user, role=ParticipantRole.VERIFIER,
        ).exists())
        self.assertTrue(
            any("Carga de Observacion" in item["comment"] for item in load_response.data["status_history"])
        )

        action_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions-taken/",
            {
                "action_completed_at": timezone.localdate().isoformat(),
                "actions_taken": "Se ajusto el proceso y se comunico al responsable",
                "effectiveness_due_at": timezone.localdate().isoformat(),
            },
            format="json",
        )

        self.assertEqual(action_response.status_code, status.HTTP_200_OK)
        self.assertEqual(action_response.data["current_status"], AnomalyStatus.PENDING_VERIFICATION)
        self.assertEqual(action_response.data["current_stage"], AnomalyStage.EFFECTIVENESS_VERIFICATION)
        self.assertTrue(
            any("Acciones tomadas" in item["comment"] for item in action_response.data["status_history"])
        )

        evidence = SimpleUploadedFile("evidencia.txt", b"ok", content_type="text/plain")
        upload_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/attachments/",
            {"file": evidence, "original_name": "evidencia.txt", "content_type": "text/plain"},
            format="multipart",
        )

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)

        missing_verification_evidence = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "Intento sin evidencia de verificacion",
            },
            format="json",
        )
        self.assertEqual(missing_verification_evidence.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("evidences", missing_verification_evidence.data)

        ineffective_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "No eficaz, requiere nueva accion",
                "evidences": SimpleUploadedFile("verificacion-1.txt", b"Resultado no eficaz", content_type="text/plain"),
            },
            format="multipart",
        )

        self.assertEqual(ineffective_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ineffective_response.data["current_status"], AnomalyStatus.IN_TREATMENT)
        self.assertEqual(ineffective_response.data["current_stage"], AnomalyStage.EXECUTION_AND_FOLLOW_UP)
        self.assertTrue(AnomalyParticipant.objects.filter(
            anomaly=anomaly, user=self.user, role=ParticipantRole.VERIFIER,
        ).exists())
        self.assertIsNone(ineffective_response.data["closed_at"])
        self.assertTrue(
            any("Evidencia cargada" in item["comment"] for item in ineffective_response.data["status_history"])
        )
        self.assertTrue(
            any("No eficaz" in item["comment"] for item in ineffective_response.data["status_history"])
        )

        effective_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "Eficaz",
                "closure_comment": "Cierre por verificacion eficaz",
                "evidences": SimpleUploadedFile("verificacion-2.txt", b"Resultado eficaz", content_type="text/plain"),
            },
            format="multipart",
        )

        self.assertEqual(effective_response.status_code, status.HTTP_200_OK)
        self.assertEqual(effective_response.data["current_status"], AnomalyStatus.CLOSED)
        self.assertEqual(effective_response.data["current_stage"], AnomalyStage.CLOSURE)
        self.assertTrue(
            any("Anomalia cerrada" in item["comment"] for item in effective_response.data["status_history"])
        )

    def test_effective_observation_is_available_for_learned_lessons(self):
        anomaly = self._immediate_anomaly("OBS-LESSON-001")
        verified_at = timezone.now()
        anomaly.owner = self.user
        anomaly.observation_resolution_path = ObservationResolutionPath.OBSERVATION
        anomaly.current_stage = AnomalyStage.CLOSURE
        anomaly.current_status = AnomalyStatus.CLOSED
        anomaly.closed_at = verified_at
        anomaly.save(
            update_fields=[
                "owner",
                "observation_resolution_path",
                "current_stage",
                "current_status",
                "closed_at",
                "updated_at",
            ]
        )
        AnomalyImmediateAction.objects.create(
            anomaly=anomaly,
            responsible=self.user,
            action_date=timezone.localdate(),
            observation="Observacion eficaz con aprendizaje pendiente.",
            effectiveness_verified_at=verified_at,
            effectiveness_is_effective=True,
            created_by=self.user,
            updated_by=self.user,
        )

        list_response = self.client.get("/api/v1/anomalies/observation-learned-lessons/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        result = next(item for item in list_response.data["results"] if item["id"] == str(anomaly.pk))
        self.assertEqual(result["code"], anomaly.code)
        self.assertIsNone(result["learning"])

        save_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/learning/",
            {
                "has_learning": "true",
                "learned_text": "Se debe verificar el ajuste antes de liberar el proceso.",
                "no_learning_reason": "",
                "procedure_modified": "true",
                "procedure_modification_notes": "Actualizar el procedimiento de inspeccion.",
                "confirm_modification": "false",
                "evidences": SimpleUploadedFile(
                    "aprendizaje-observacion.pdf",
                    b"%PDF-1.4 evidencia de aprendizaje",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            save_response.data["learned_text"],
            "Se debe verificar el ajuste antes de liberar el proceso.",
        )
        self.assertTrue(save_response.data["procedure_modified"])
        self.assertEqual(len(save_response.data["evidences"]), 1)

        unconfirmed_update = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/learning/",
            {
                "has_learning": "false",
                "no_learning_reason": "No surgieron cambios adicionales.",
                "procedure_modified": "false",
            },
            format="multipart",
        )
        self.assertEqual(unconfirmed_update.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_modification", unconfirmed_update.data)

        refreshed_list = self.client.get("/api/v1/anomalies/observation-learned-lessons/")
        refreshed_result = next(
            item for item in refreshed_list.data["results"] if item["id"] == str(anomaly.pk)
        )
        self.assertEqual(
            refreshed_result["learning"]["learned_text"],
            "Se debe verificar el ajuste antes de liberar el proceso.",
        )
        self.assertEqual(len(refreshed_result["learning"]["evidences"]), 1)

    def test_observation_trt_creates_treatment_immediately(self):
        anomaly = self._immediate_anomaly("AI-TRT-001")
        anomaly.severity = self.severity_observation
        anomaly.save(update_fields=["severity", "updated_at"])

        response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
                "observation": "La observacion requiere analisis de causa y tratamiento.",
                "requires_treatment": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["observation_resolution_path"], ObservationResolutionPath.TREATMENT)
        self.assertEqual(response.data["severity"]["id"], str(self.severity_observation.pk))
        self.assertTrue(response.data["code"].endswith("-OBS"))
        self.assertIn("Observacion TRT", response.data["classification_summary"])
        self.assertTrue(
            any("Observacion TRT confirmada" in item["comment"] for item in response.data["status_history"])
        )
        treatment = Treatment.objects.get(primary_anomaly=anomaly)
        self.assertEqual(treatment.responsible_id, self.user.pk)

        observation_list = self.client.get("/api/v1/anomalies/immediate-actions/")
        observation_ids = {item["id"] for item in observation_list.data["results"]}
        self.assertNotIn(str(anomaly.pk), observation_ids)

    def test_observation_supports_multiple_read_only_actions(self):
        anomaly = self._immediate_anomaly("OBS-MULTI-001")
        load_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
                "observation": "Datos generales confirmados.",
            },
            format="json",
        )
        self.assertEqual(load_response.status_code, status.HTTP_200_OK)

        for sequence in (1, 2):
            response = self.client.post(
                f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
                {
                    "detail": f"Accion independiente {sequence}",
                    "estimated_completion_date": (timezone.localdate() + timedelta(days=sequence)).isoformat(),
                    "effectiveness_due_date": (timezone.localdate() + timedelta(days=sequence + 5)).isoformat(),
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["sequence"], sequence)
            self.assertEqual(response.data["status"], "pending")

        detail = self.client.get(f"/api/v1/anomalies/{anomaly.pk}/")
        self.assertEqual(len(detail.data["observation_actions"]), 2)
        self.assertEqual(
            [item["detail"] for item in detail.data["observation_actions"]],
            ["Accion independiente 1", "Accion independiente 2"],
        )

    def test_observation_action_can_be_finalized_without_editing_its_content(self):
        anomaly = self._immediate_anomaly("OBS-COMPLETE-001")
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Datos generales confirmados.",
            },
            format="json",
        )
        create_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
            {
                "detail": "Accion que debe permanecer inmutable.",
                "estimated_completion_date": timezone.localdate().isoformat(),
                "effectiveness_due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            },
            format="json",
        )

        blocked = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{create_response.data['id']}/complete/",
            {"completed_at": timezone.localdate().isoformat()}, format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("evidence", blocked.data)
        uploaded = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{create_response.data['id']}/evidences/",
            {"file": SimpleUploadedFile("evidencia.txt", b"Trabajo realizado", content_type="text/plain"), "note": "Evidencia propia"},
            format="multipart",
        )
        self.assertEqual(uploaded.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(uploaded.data["observation_action"]), create_response.data["id"])
        self.assertEqual(uploaded.data["note"], "Evidencia propia")
        detail = self.client.get(f"/api/v1/anomalies/{anomaly.pk}/")
        action_evidence = next(item for item in detail.data["attachments"] if item["id"] == uploaded.data["id"])
        self.assertEqual(str(action_evidence["observation_action"]), create_response.data["id"])
        pending_action = ObservationAction.objects.get(pk=create_response.data["id"])
        self.assertEqual(pending_action.status, "pending")
        self.assertIsNone(pending_action.completed_at)
        work_items = self.client.get("/api/v1/actions/work-items/?source=observation")
        work_item = next(item for item in work_items.data["results"] if item["id"] == create_response.data["id"])
        self.assertEqual(work_item["evidences"][0]["id"], uploaded.data["id"])
        self.assertEqual(work_item["status"], "pending")
        self.assertTrue(work_item["can_update_status"])
        self.assertIn("attachments/", work_item["evidences"][0]["file_url"])
        complete_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{create_response.data['id']}/complete/",
            {"completed_at": timezone.localdate().isoformat()},
            format="json",
        )

        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_response.data["status"], "completed")
        action = ObservationAction.objects.get(pk=create_response.data["id"])
        self.assertEqual(action.detail, "Accion que debe permanecer inmutable.")
        self.assertEqual(action.completed_by_id, self.user.pk)
        self.assertTrue(
            anomaly.status_history.filter(comment__contains="finalizada").exists()
        )

    def test_observation_actions_advance_to_effectiveness_and_use_latest_due_date(self):
        anomaly = self._immediate_anomaly("OBS-EFFECTIVENESS-001")
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Datos generales confirmados.",
            },
            format="json",
        )
        created_actions = []
        for sequence, due_days in ((1, -2), (2, 0)):
            response = self.client.post(
                f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
                {
                    "detail": f"Accion para eficacia {sequence}",
                    "estimated_completion_date": (timezone.localdate() + timedelta(days=sequence)).isoformat(),
                    "effectiveness_due_date": (timezone.localdate() + timedelta(days=due_days)).isoformat(),
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_actions.append(response.data)

        pending_effectiveness = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "Eficaz con una accion pendiente.",
            },
            format="json",
        )
        self.assertEqual(pending_effectiveness.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("actions", pending_effectiveness.data)

        for action in created_actions:
            blocked = self.client.post(
                f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action['id']}/complete/",
                {"completed_at": timezone.localdate().isoformat()}, format="json",
            )
            self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("evidence", blocked.data)
            uploaded = self.client.post(
                f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action['id']}/evidences/",
                {"file": SimpleUploadedFile("evidencia.txt", b"Trabajo realizado", content_type="text/plain")},
                format="multipart",
            )
            self.assertEqual(uploaded.status_code, status.HTTP_201_CREATED)
            complete_response = self.client.post(
                f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action['id']}/complete/",
                {"completed_at": timezone.localdate().isoformat()},
                format="json",
            )
            self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
            anomaly.refresh_from_db()
            if action != created_actions[-1]:
                self.assertEqual(anomaly.current_status, AnomalyStatus.IN_TREATMENT)

        anomaly.refresh_from_db()
        self.assertEqual(anomaly.current_status, AnomalyStatus.PENDING_VERIFICATION)
        self.assertEqual(anomaly.current_stage, AnomalyStage.EFFECTIVENESS_VERIFICATION)
        self.assertTrue(
            anomaly.status_history.filter(comment__contains="continua la verificacion de eficacia").exists()
        )

        effective_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "Todas las acciones fueron eficaces.",
                "evidences": SimpleUploadedFile("verificacion.txt", b"Resultado eficaz", content_type="text/plain"),
            },
            format="multipart",
        )
        self.assertEqual(effective_response.status_code, status.HTTP_200_OK)
        self.assertEqual(effective_response.data["current_status"], AnomalyStatus.CLOSED)
        self.assertEqual(effective_response.data["current_stage"], AnomalyStage.CLOSURE)

    def test_not_effective_observation_allows_a_new_action_without_losing_history(self):
        anomaly = self._immediate_anomaly("OBS-REOPEN-001")
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Datos generales confirmados.",
            },
            format="json",
        )
        action_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
            {
                "detail": "Primera accion.",
                "estimated_completion_date": timezone.localdate().isoformat(),
                "effectiveness_due_date": timezone.localdate().isoformat(),
            },
            format="json",
        )
        uploaded = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action_response.data['id']}/evidences/",
            {"file": SimpleUploadedFile("evidencia.txt", b"Trabajo realizado", content_type="text/plain")},
            format="multipart",
        )
        self.assertEqual(uploaded.status_code, status.HTTP_201_CREATED)
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action_response.data['id']}/complete/",
            {"completed_at": timezone.localdate().isoformat()},
            format="json",
        )

        ineffective_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "La accion no resolvio el desvio.",
                "evidences": SimpleUploadedFile("verificacion.txt", b"Resultado no eficaz", content_type="text/plain"),
            },
            format="multipart",
        )
        self.assertEqual(ineffective_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ineffective_response.data["current_status"], AnomalyStatus.IN_TREATMENT)
        self.assertEqual(len(ineffective_response.data["effectiveness_checks"]), 1)

        new_action_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
            {
                "detail": "Accion correctiva del nuevo ciclo.",
                "estimated_completion_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "effectiveness_due_date": (timezone.localdate() + timedelta(days=7)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(new_action_response.status_code, status.HTTP_201_CREATED)
        detail = self.client.get(f"/api/v1/anomalies/{anomaly.pk}/")
        self.assertEqual(len(detail.data["effectiveness_checks"]), 1)
        self.assertIsNone(detail.data["immediate_action"]["effectiveness_verified_at"])
        self.assertIsNone(detail.data["immediate_action"]["effectiveness_is_effective"])

    def test_observation_effectiveness_requires_at_least_one_action(self):
        anomaly = self._immediate_anomaly("OBS-NO-ACTION-001")
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Datos generales sin acciones.",
            },
            format="json",
        )

        response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "Intento sin acciones.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("actions_taken", response.data)
        anomaly.refresh_from_db()
        self.assertNotEqual(anomaly.current_status, AnomalyStatus.CLOSED)

    def test_observation_effectiveness_requires_effectiveness_basis(self):
        anomaly = self._immediate_anomaly("OBS-BASIS-001")
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Causa asignada confirmada.",
            },
            format="json",
        )
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions-taken/",
            {
                "action_completed_at": timezone.localdate().isoformat(),
                "actions_taken": "Accion terminada.",
                "effectiveness_due_at": timezone.localdate().isoformat(),
            },
            format="json",
        )

        response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effectiveness_comment", response.data)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.current_status, AnomalyStatus.PENDING_VERIFICATION)
        self.assertFalse(anomaly.effectiveness_checks.exists())

    def test_observation_effectiveness_cannot_be_verified_before_due_date(self):
        anomaly = self._immediate_anomaly("OBS-EARLY-VERIFY-001")
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Causa asignada por el responsable.",
            },
            format="json",
        )
        action_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
            {
                "detail": "Accion con verificacion futura.",
                "estimated_completion_date": timezone.localdate().isoformat(),
                "effectiveness_due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            },
            format="json",
        )
        uploaded = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action_response.data['id']}/evidences/",
            {"file": SimpleUploadedFile("evidencia.txt", b"Trabajo realizado", content_type="text/plain")},
            format="multipart",
        )
        self.assertEqual(uploaded.status_code, status.HTTP_201_CREATED)
        self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/{action_response.data['id']}/complete/",
            {"completed_at": timezone.localdate().isoformat()},
            format="json",
        )

        response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "Intento anticipado.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effectiveness_verified_at", response.data)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.current_status, AnomalyStatus.PENDING_VERIFICATION)
        self.assertFalse(anomaly.effectiveness_checks.exists())

    def test_unassigned_user_cannot_manage_observation_actions_or_effectiveness(self):
        responsible = User.objects.create_user(
            username="responsable_fase4",
            email="responsable_fase4@example.com",
            password="secret123",
            primary_sector=self.area,
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        unassigned = User.objects.create_user(
            username="no_asignado_fase4",
            email="no_asignado_fase4@example.com",
            password="secret123",
            primary_sector=self.area,
            access_level=User.AccessLevel.MANDO_MEDIO_ACTIVO,
        )
        anomaly = self._immediate_anomaly("OBS-PERMISSION-001")
        load_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(responsible.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Observacion asignada.",
            },
            format="json",
        )
        self.assertEqual(load_response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=unassigned)
        action_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions/",
            {
                "detail": "Accion no autorizada.",
                "estimated_completion_date": timezone.localdate().isoformat(),
                "effectiveness_due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            },
            format="json",
        )
        effectiveness_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": True,
                "effectiveness_comment": "Verificacion no autorizada.",
            },
            format="json",
        )

        self.assertEqual(action_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(effectiveness_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(ObservationAction.objects.filter(anomaly=anomaly).exists())

    def test_observation_cannot_be_marked_as_trt_after_actions_are_confirmed(self):
        anomaly = self._immediate_anomaly("AI-TRT-BLOCKED")
        anomaly.severity = self.severity_observation
        anomaly.owner = self.user
        anomaly.save(update_fields=["severity", "owner", "updated_at"])
        action_date = (timezone.localdate() + timedelta(days=3)).isoformat()

        load_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": action_date,
                "observation": "Observacion gestionada sin tratamiento.",
            },
            format="json",
        )
        self.assertEqual(load_response.status_code, status.HTTP_200_OK)

        actions_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions-taken/",
            {
                "action_completed_at": timezone.localdate().isoformat(),
                "actions_taken": "Acciones directas confirmadas.",
                "effectiveness_due_at": (timezone.localdate() + timedelta(days=7)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(actions_response.status_code, status.HTTP_200_OK)

        trt_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": action_date,
                "observation": "Intento posterior de derivacion.",
                "requires_treatment": True,
            },
            format="json",
        )

        self.assertEqual(trt_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requires_treatment", trt_response.data)
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.observation_resolution_path, ObservationResolutionPath.OBSERVATION)
        self.assertEqual(anomaly.immediate_action.actions_taken, "Acciones directas confirmadas.")

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True)
    def test_observation_action_assigns_effectiveness_verification_without_duplicates(self):
        self.user.email_notifications_enabled = True
        self.user.save(update_fields=["email_notifications_enabled", "updated_at"])
        anomaly = self._immediate_anomaly("AI-NOTIFY-001")
        due_date = timezone.localdate()

        load_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/load/",
            {
                "responsible": str(self.user.pk),
                "action_date": timezone.localdate().isoformat(),
                "observation": "Observación con verificación asignada",
            },
            format="json",
        )
        self.assertEqual(load_response.status_code, status.HTTP_200_OK)

        payload = {
            "action_completed_at": timezone.localdate().isoformat(),
            "actions_taken": "Se corrigió el desvío observado",
            "effectiveness_due_at": due_date.isoformat(),
        }
        first_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions-taken/",
            payload,
            format="json",
        )
        second_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions-taken/",
            payload,
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        notifications = Notification.objects.filter(
            template_code="observation_effectiveness_assigned",
            source_id=anomaly.pk,
        )
        self.assertEqual(notifications.count(), 1)
        notification = notifications.get()
        self.assertEqual(notification.task_type, NotificationTaskType.VERIFICATION_PARTICIPATION)
        self.assertEqual(timezone.localtime(notification.due_at).date(), due_date)
        self.assertFalse(notification.context_data["include_action_url_in_email"])
        recipients = NotificationRecipient.objects.filter(notification=notification, user=self.user)
        self.assertEqual(recipients.count(), 2)

        effectiveness_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "Debe repetirse la acción",
                "evidences": SimpleUploadedFile("verificacion.txt", b"Resultado no eficaz", content_type="text/plain"),
            },
            format="multipart",
        )
        self.assertEqual(effectiveness_response.status_code, status.HTTP_200_OK)
        in_app = recipients.get(channel=NotificationChannel.IN_APP)
        email = recipients.get(channel=NotificationChannel.EMAIL)
        self.assertEqual(in_app.task_status, RecipientTaskStatus.COMPLETED)
        self.assertEqual(email.delivery_status, DeliveryStatus.SKIPPED)

    def test_usuario_activo_can_create_anomaly(self):
        active_user = User.objects.create_user(
            username="operario1",
            email="operario1@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        self.client.force_authenticate(user=active_user)

        payload = self._build_payload("004", include_severity=False)
        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reporter"]["id"], str(active_user.pk))

    def test_admin_access_level_user_can_list_all_anomalies(self):
        reporter_a = User.objects.create_user(
            username="usuarioa",
            email="usuarioa@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        reporter_b = User.objects.create_user(
            username="usuariob",
            email="usuariob@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        admin_user = User.objects.create_user(
            username="adminnivel",
            email="adminnivel@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
            primary_sector=self.area,
        )

        year = timezone.localdate().year
        Anomaly.objects.create(
            code=f"{year}9001",
            title="Anomalia A",
            description="Detalle A",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area,
            reporter=reporter_a,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        Anomaly.objects.create(
            code=f"{year}9002",
            title="Anomalia B",
            description="Detalle B",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area,
            reporter=reporter_b,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.get("/api/v1/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {item["code"] for item in response.data["results"]}
        self.assertIn(f"{year}9001", codes)
        self.assertIn(f"{year}9002", codes)

    def test_tracking_list_includes_associated_treatment_anomalies(self):
        year = timezone.localdate().year
        parent = Anomaly.objects.create(
            code=f"{year}9010",
            title="Anomalia principal",
            description="Caso principal del tratamiento",
            current_status=AnomalyStatus.IN_TREATMENT,
            current_stage=AnomalyStage.ACTION_PLAN,
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        child = Anomaly.objects.create(
            code=f"{year}9011",
            title="Anomalia hija",
            description="Caso asociado al tratamiento",
            current_status=AnomalyStatus.IN_TREATMENT,
            current_stage=AnomalyStage.ACTION_PLAN,
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        treatment = Treatment.objects.create(
            code="TRT-TRACKING-001",
            primary_anomaly=parent,
            responsible=self.user,
            created_by=self.user,
            updated_by=self.user,
        )
        TreatmentAnomaly.objects.create(
            treatment=treatment,
            anomaly=parent,
            is_primary=True,
            created_by=self.user,
            updated_by=self.user,
        )
        TreatmentAnomaly.objects.create(
            treatment=treatment,
            anomaly=child,
            is_primary=False,
            created_by=self.user,
            updated_by=self.user,
        )

        response = self.client.get("/api/v1/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        anomaly_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(parent.pk), anomaly_ids)
        self.assertIn(str(child.pk), anomaly_ids)

        detail_response = self.client.get(f"/api/v1/anomalies/{child.pk}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

    def test_default_tracking_order_prioritizes_registered_and_sends_closed_last(self):
        admin_user = User.objects.create_user(
            username="adminorden",
            email="adminorden@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
            primary_sector=self.area,
        )
        year = timezone.localdate().year
        now = timezone.now()

        closed = Anomaly.objects.create(
            code=f"{year}9020",
            title="Orden seguimiento",
            description="Cerrada reciente",
            current_status=AnomalyStatus.CLOSED,
            current_stage=AnomalyStage.CLOSURE,
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=now,
            created_by=self.user,
            updated_by=self.user,
        )
        middle = Anomaly.objects.create(
            code=f"{year}9021",
            title="Orden seguimiento",
            description="En analisis intermedia",
            current_status=AnomalyStatus.IN_ANALYSIS,
            current_stage=AnomalyStage.CAUSE_ANALYSIS,
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=now - timedelta(minutes=1),
            created_by=self.user,
            updated_by=self.user,
        )
        registered = Anomaly.objects.create(
            code=f"{year}9022",
            title="Orden seguimiento",
            description="Registrada antigua",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=now - timedelta(minutes=2),
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.get("/api/v1/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"][:3]],
            [str(registered.pk), str(middle.pk), str(closed.pk)],
        )

        search_response = self.client.get("/api/v1/anomalies/?search=Orden%20seguimiento")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in search_response.data["results"][:3]],
            [str(closed.pk), str(middle.pk), str(registered.pk)],
        )


    def test_admin_can_search_anomalies_by_assigned_area_and_status_not_reporter(self):
        reporter_a = User.objects.create_user(
            username="usuario_busqueda",
            email="busqueda@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
            first_name="Lucia",
            last_name="Perez",
        )
        reporter_b = User.objects.create_user(
            username="otro_usuario",
            email="otro@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
            first_name="Carlos",
            last_name="Lopez",
        )
        admin_user = User.objects.create_user(
            username="adminbusqueda",
            email="adminbusqueda@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
            primary_sector=self.area,
        )

        year = timezone.localdate().year
        assigned_area = Area.objects.create(site=self.site, code="A02", name="Area asignada")
        Anomaly.objects.create(
            code=f"{year}9010",
            title="Anomalia registrada",
            description="Detalle",
            current_status=AnomalyStatus.REGISTERED,
            current_stage=AnomalyStage.REGISTRATION,
            site=self.site,
            area=self.area,
            imputed_area=assigned_area,
            reporter=reporter_a,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        anomaly_b = Anomaly.objects.create(
            code=f"{year}9011",
            title="Anomalia de Carlos",
            description="Detalle",
            current_status=AnomalyStatus.IN_ANALYSIS,
            current_stage=AnomalyStage.CAUSE_ANALYSIS,
            site=self.site,
            area=self.area,
            imputed_area=assigned_area,
            reporter=reporter_b,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=admin_user)

        response_reporter = self.client.get("/api/v1/anomalies/?search=Lucia")
        self.assertEqual(response_reporter.status_code, status.HTTP_200_OK)
        self.assertEqual(response_reporter.data["count"], 0)

        response_assigned_area = self.client.get("/api/v1/anomalies/?search=Area asignada")
        self.assertEqual(response_assigned_area.status_code, status.HTTP_200_OK)
        self.assertEqual(response_assigned_area.data["count"], 2)

        response_origin_area = self.client.get("/api/v1/anomalies/?search=Area 1")
        self.assertEqual(response_origin_area.status_code, status.HTTP_200_OK)
        self.assertEqual(response_origin_area.data["count"], 0)

        response_status = self.client.get("/api/v1/anomalies/?search=en%20an%C3%A1lisis")
        self.assertEqual(response_status.status_code, status.HTTP_200_OK)
        self.assertEqual(response_status.data["count"], 1)
        self.assertEqual(response_status.data["results"][0]["id"], str(anomaly_b.pk))

        response_status_without_accent = self.client.get("/api/v1/anomalies/?search=analisis")
        self.assertEqual(response_status_without_accent.status_code, status.HTTP_200_OK)
        self.assertEqual(response_status_without_accent.data["count"], 1)
        self.assertEqual(response_status_without_accent.data["results"][0]["id"], str(anomaly_b.pk))

    def test_repetition_study_groups_by_type_assigned_area_and_finding_type(self):
        admin_user = User.objects.create_user(
            username="adminrepitencia",
            email="adminrepitencia@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
            primary_sector=self.area,
        )
        year = timezone.localdate().year

        first = Anomaly.objects.create(
            code=f"{year}9030",
            title="Repitencia triple A",
            description="Mismo desvio y proceso, hallazgo alto",
            current_status=AnomalyStatus.IN_ANALYSIS,
            current_stage=AnomalyStage.CAUSE_ANALYSIS,
            site=self.site,
            area=self.area,
            imputed_area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        second = Anomaly.objects.create(
            code=f"{year}9031",
            title="Repitencia triple B",
            description="Mismo desvio y proceso, hallazgo medio",
            current_status=AnomalyStatus.IN_ANALYSIS,
            current_stage=AnomalyStage.CAUSE_ANALYSIS,
            site=self.site,
            area=self.area,
            imputed_area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity_alt,
            priority=self.priority,
            detected_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.get(f"/api/v1/anomalies/repetition-study/?date_from={timezone.localdate().isoformat()}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        matching_rows = [
            item for item in response.data["by_type_sector"]
            if item["type_id"] == str(self.anomaly_type.pk) and item["sector_id"] == str(self.area.pk)
        ]
        self.assertEqual({item["finding_type_id"] for item in matching_rows}, {str(self.severity.pk), str(self.severity_alt.pk)})
        self.assertEqual({item["finding_type_name"] for item in matching_rows}, {self.severity.name, self.severity_alt.name})
        self.assertTrue(all(item["count"] == 1 for item in matching_rows))

        anomalies_by_id = {item["id"]: item for item in response.data["anomalies"]}
        self.assertEqual(anomalies_by_id[str(first.pk)]["finding_type"]["id"], str(self.severity.pk))
        self.assertEqual(anomalies_by_id[str(second.pk)]["finding_type"]["id"], str(self.severity_alt.pk))

    def test_improvement_opportunity_does_not_classify_anomaly(self):
        opportunity = Severity.objects.create(code="OPM", name="Oportunidad de mejora")
        create_response = self.client.post(
            "/api/v1/anomalies/", self._build_payload("OM-001", include_severity=False), format="json"
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]
        patch_response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(opportunity),
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_400_BAD_REQUEST)
        anomaly = Anomaly.objects.get(pk=anomaly_id)
        self.assertIsNone(anomaly.severity_id)
        self.assertFalse(AnomalyClassification.objects.filter(anomaly=anomaly).exists())
        self.assertFalse(AnomalyInitialVerification.objects.filter(anomaly=anomaly).exists())

    def test_admin_classification_registers_verification_and_classification_records(self):
        payload = self._build_payload("005", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]
        patch_response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(self.severity),
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["current_stage"], AnomalyStage.CLASSIFICATION)
        self.assertEqual(patch_response.data["current_status"], AnomalyStatus.IN_EVALUATION)

        self.assertIsNotNone(patch_response.data["initial_verification"])
        self.assertIsNotNone(patch_response.data["classification"])
        self.assertIn("Criterio de Revisión de hallazgos aplicado", patch_response.data["classification"]["summary"])
        self.assertIn(self.severity.name, patch_response.data["classification"]["summary"])

        participant_exists = AnomalyParticipant.objects.filter(
            anomaly_id=anomaly_id,
            user=self.user,
            role=ParticipantRole.VERIFIER,
        ).exists()
        self.assertTrue(participant_exists)

        owner_exists = AnomalyParticipant.objects.filter(
            anomaly_id=anomaly_id,
            user=self.user,
            role=ParticipantRole.OWNER,
        ).exists()
        self.assertTrue(owner_exists)
        self.assertEqual(patch_response.data["owner"]["id"], str(self.user.pk))
        self.assertTrue(
            any("Responsable asignado" in item["evidence_note"] for item in patch_response.data["status_history"])
        )

    def test_detail_separates_anomaly_intervenients_and_convocation_without_actions(self):
        anomaly = self._immediate_anomaly("OBS-CONVOCATION")
        reporter = User.objects.create_user(username="convocation-reporter", email="convocation-reporter@example.com")
        manager = User.objects.create_user(username="convocation-manager", email="convocation-manager@example.com", access_level="mando_medio_activo")
        invited = User.objects.create_user(username="convocation-invited", email="convocation-invited@example.com")
        anomaly.reporter = reporter
        anomaly.owner = manager
        anomaly.save()
        for user, role in [(reporter, "reporter"), (manager, "owner"), (self.user, "verifier")]:
            AnomalyParticipant.objects.create(anomaly=anomaly, user=user, role=role)
        treatment = Treatment.objects.create(code="TRT-CONVOCATION", primary_anomaly=anomaly, responsible=manager)
        TreatmentParticipant.objects.create(treatment=treatment, user=manager, role="owner")
        TreatmentParticipant.objects.create(treatment=treatment, user=invited, role="convoked")

        response = self.client.get(f"/api/v1/anomalies/{anomaly.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["treatment_tasks"], [])
        self.assertEqual({p["user"]["id"] for p in response.data["participants"]}, {str(reporter.pk), str(manager.pk), str(self.user.pk)})
        self.assertEqual({p["user"]["id"] for p in response.data["treatments"][0]["participants"]}, {str(manager.pk), str(invited.pk)})
        secondary = self._immediate_anomaly("OBS-SECONDARY-CONVOCATION")
        TreatmentAnomaly.objects.create(treatment=treatment, anomaly=secondary, is_primary=False)
        response = self.client.get(f"/api/v1/anomalies/{secondary.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["treatments"][0]["id"], str(treatment.pk))

    def test_verifier_cleanup_preserves_real_verifications_and_manual_assignments(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection

        anomaly = self._immediate_anomaly("OBS-ROLE-CLEANUP")
        legacy_note = "Registra y verifica cierre por Observacion."
        premature = User.objects.create_user(username="premature-verifier", email="premature@example.com")
        actual = User.objects.create_user(username="actual-verifier", email="actual@example.com")
        historical = User.objects.create_user(username="historical-verifier", email="historical@example.com")
        for user in [self.user, premature, actual, historical]:
            AnomalyParticipant.objects.create(anomaly=anomaly, user=user, role="verifier", note=legacy_note)
        AnomalyParticipant.objects.create(anomaly=anomaly, user=premature, role="owner")
        manual = AnomalyParticipant.objects.create(anomaly=anomaly, user=premature, role="observer", note="Seguimiento manual")
        AnomalyEffectivenessCheck.objects.create(
            anomaly=anomaly, verified_by=actual, verified_at=timezone.now(),
            is_effective=True, comment="Verificación real", evidence_summary="Muestra conforme",
        )
        treatment = Treatment.objects.create(code="TRT-ROLE-CLEANUP", primary_anomaly=anomaly, responsible=self.user)
        AuditEvent.objects.create(
            entity_type="actions.treatment", entity_id=treatment.pk,
            action="treatment.effectiveness_validated", actor=historical,
        )
        migrate = import_module("apps.anomalies.migrations.0022_correct_observation_verifier_roles").correct_observation_verifier_roles
        migrate(apps, SimpleNamespace(connection=connection))

        self.assertFalse(AnomalyParticipant.objects.filter(anomaly=anomaly, user=premature, role="verifier").exists())
        self.assertTrue(AnomalyParticipant.objects.filter(anomaly=anomaly, user=premature, role="owner").exists())
        self.assertTrue(AnomalyParticipant.objects.filter(pk=manual.pk).exists())
        for user in [self.user, actual, historical]:
            self.assertTrue(AnomalyParticipant.objects.filter(anomaly=anomaly, user=user, role="verifier").exists())
        audit = AuditEvent.objects.filter(entity_id=anomaly.pk, action="anomaly.participant_role_corrected")
        self.assertEqual(audit.count(), 4)
        migrate(apps, SimpleNamespace(connection=connection))
        self.assertEqual(audit.count(), 4)

    def test_valid_classification_requires_responsible(self):
        payload = self._build_payload("011", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        response = self.client.patch(
            f"/api/v1/anomalies/{create_response.data['id']}/",
            {"severity": str(self.severity.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("classification_responsible", response.data)

    def test_non_admin_cannot_classify_even_with_permissions(self):
        permissions = ensure_required_permissions()
        non_admin = User.objects.create_user(
            username="clasificador_no_admin",
            email="clasificador_no_admin@example.com",
            password="secret123",
            access_level=User.AccessLevel.USUARIO_ACTIVO,
            primary_sector=self.area,
        )
        non_admin.user_permissions.add(
            permissions[PERMISSION_EDIT_ANOMALY],
            permissions[PERMISSION_CLASSIFY_ANOMALY],
        )

        payload = self._build_payload("013", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        anomaly_id = create_response.data["id"]
        Anomaly.objects.filter(pk=anomaly_id).update(reporter=non_admin)

        self.client.force_authenticate(user=non_admin)
        patch_response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(self.severity),
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Solo usuarios ADMIN", str(patch_response.data))

        direct_response = self.client.post(
            f"/api/v1/anomalies/{anomaly_id}/classification/",
            {
                "containment_required": True,
                "requires_action_plan": True,
                "requires_effectiveness_verification": True,
                "summary": "Intento no admin",
            },
            format="json",
        )

        self.assertEqual(direct_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Solo usuarios ADMIN", str(direct_response.data))

        unlock_response = self.client.post(f"/api/v1/anomalies/{anomaly_id}/classification/unlock/", {}, format="json")

        self.assertEqual(unlock_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Solo usuarios ADMIN", str(unlock_response.data))

    def test_invalid_classification_requires_reason_and_closes_anomaly(self):
        payload = self._build_payload("012", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        anomaly_id = create_response.data["id"]

        missing_reason = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity_invalid.pk)},
            format="json",
        )

        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("classification_reason", missing_reason.data)

        response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {
                "severity": str(self.severity_invalid.pk),
                "classification_reason": "No corresponde gestionar como anomalia.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], AnomalyStatus.CLOSED)
        self.assertEqual(response.data["current_stage"], AnomalyStage.CLOSURE)
        self.assertIsNotNone(response.data["closed_at"])
        self.assertIn("No corresponde gestionar como anomalia", response.data["closure_comment"])
        self.assertEqual(response.data["classification"]["requires_action_plan"], False)
        self.assertTrue(
            any("Resultado: Invalida" in item["evidence_note"] for item in response.data["status_history"])
        )
        self.assertTrue(
            Notification.objects.filter(
                source_id=anomaly_id,
                template_code="anomaly_closed",
                context_data__closure_path="invalid",
            ).exists()
        )





    def test_classification_only_allows_one_change_without_unlock(self):
        payload = self._build_payload("007", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]

        first_classification = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(self.severity),
            format="json",
        )
        self.assertEqual(first_classification.status_code, status.HTTP_200_OK)

        second_classification = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(self.severity_alt),
            format="json",
        )
        self.assertEqual(second_classification.status_code, status.HTTP_200_OK)
        self.assertEqual(second_classification.data["classification_change_count"], 1)
        self.assertFalse(second_classification.data["can_modify_classification"])
        self.assertTrue(second_classification.data["can_unlock_classification"])

        blocked_change = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(self.severity_extra),
            format="json",
        )
        self.assertEqual(blocked_change.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No se puede modificar la Revisión de hallazgos", str(blocked_change.data))

        unlock_response = self.client.post(f"/api/v1/anomalies/{anomaly_id}/classification/unlock/", {}, format="json")
        self.assertEqual(unlock_response.status_code, status.HTTP_200_OK)
        self.assertTrue(unlock_response.data["can_modify_classification"])

        unlocked_change = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(self.severity_extra),
            format="json",
        )
        self.assertEqual(unlocked_change.status_code, status.HTTP_200_OK)
        self.assertEqual(unlocked_change.data["severity"]["id"], str(self.severity_extra.pk))

    def test_unlock_classification_is_blocked_after_stage_advanced(self):
        payload = self._build_payload("008", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly = Anomaly.objects.get(pk=create_response.data["id"])
        anomaly.severity = self.severity
        anomaly.current_stage = AnomalyStage.CAUSE_ANALYSIS
        anomaly.current_status = AnomalyStatus.IN_ANALYSIS
        anomaly.updated_by = self.user
        anomaly.save(update_fields=["severity", "current_stage", "current_status", "updated_by", "updated_at"])

        unlock_response = self.client.post(f"/api/v1/anomalies/{anomaly.pk}/classification/unlock/", {}, format="json")
        self.assertEqual(unlock_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No se puede modificar la Revisión de hallazgos", str(unlock_response.data))


    def test_create_treatment_moves_anomaly_to_treatment_created_and_blocks_classification(self):
        payload = self._build_payload("009", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]
        nonconformity = Severity.objects.create(code="NC", name="No Conformidad")
        classify_response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            self._classification_payload(nonconformity),
            format="json",
        )
        self.assertEqual(classify_response.status_code, status.HTTP_200_OK)
        self.assertTrue(Treatment.objects.filter(primary_anomaly_id=anomaly_id).exists())

        detail_response = self.client.get(f"/api/v1/anomalies/{anomaly_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["current_stage"], AnomalyStage.TREATMENT_CREATED)
        self.assertEqual(detail_response.data["current_status"], AnomalyStatus.IN_ANALYSIS)
        self.assertFalse(detail_response.data["can_modify_classification"])
        self.assertFalse(detail_response.data["can_unlock_classification"])

        treatment_created_entries = [
            item for item in detail_response.data["status_history"] if item["to_stage"] == AnomalyStage.TREATMENT_CREATED
        ]
        self.assertTrue(treatment_created_entries)
        self.assertIn("tratamiento", treatment_created_entries[0]["comment"].lower())
