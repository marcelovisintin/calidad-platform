from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.constants import PERMISSION_CLASSIFY_ANOMALY, PERMISSION_EDIT_ANOMALY
from apps.accounts.models import User
from apps.accounts.services.role_setup import ensure_required_permissions
from apps.actions.models import Treatment
from apps.anomalies.models import (
    AffectedOrder,
    Anomaly,
    AnomalyClassification,
    AnomalyCodeReservation,
    AnomalyImmediateAction,
    AnomalyInitialVerification,
    AnomalyParticipant,
    AnomalyStage,
    AnomalyStatus,
    ObservationResolutionPath,
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
        return {"severity": str(severity.pk), "classification_responsible": str(self.user.pk)}

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
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], AnomalyStatus.PENDING_VERIFICATION)
        self.assertEqual(response.data["current_stage"], AnomalyStage.EFFECTIVENESS_VERIFICATION)
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
            },
            format="json",
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data["current_status"], AnomalyStatus.PENDING_VERIFICATION)
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
        }

        response = self.client.post(f"/api/v1/anomalies/{anomaly.pk}/immediate-action/", payload, format="json")

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
        self.assertTrue(
            any("Carga de Observacion" in item["comment"] for item in load_response.data["status_history"])
        )

        action_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/actions-taken/",
            {
                "action_completed_at": timezone.localdate().isoformat(),
                "actions_taken": "Se ajusto el proceso y se comunico al responsable",
                "effectiveness_due_at": (timezone.localdate() + timedelta(days=7)).isoformat(),
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

        ineffective_response = self.client.post(
            f"/api/v1/anomalies/{anomaly.pk}/observation/effectiveness/",
            {
                "effectiveness_verified_at": timezone.now().isoformat(),
                "effectiveness_is_effective": False,
                "effectiveness_comment": "No eficaz, requiere nueva accion",
            },
            format="json",
        )

        self.assertEqual(ineffective_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ineffective_response.data["current_status"], AnomalyStatus.PENDING_VERIFICATION)
        self.assertEqual(ineffective_response.data["current_stage"], AnomalyStage.EFFECTIVENESS_VERIFICATION)
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
            },
            format="json",
        )

        self.assertEqual(effective_response.status_code, status.HTTP_200_OK)
        self.assertEqual(effective_response.data["current_status"], AnomalyStatus.CLOSED)
        self.assertEqual(effective_response.data["current_stage"], AnomalyStage.CLOSURE)
        self.assertTrue(
            any("Anomalia cerrada" in item["comment"] for item in effective_response.data["status_history"])
        )

    def test_observation_can_be_marked_as_treatment_pending(self):
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
        self.assertEqual(response.data["observation_resolution_path"], ObservationResolutionPath.TREATMENT_PENDING)
        self.assertEqual(response.data["severity"]["id"], str(self.severity_observation.pk))
        self.assertTrue(response.data["code"].endswith("-OBS"))
        self.assertIn("Observacion TRT", response.data["classification_summary"])
        self.assertTrue(
            any("Observacion TRT confirmada" in item["comment"] for item in response.data["status_history"])
        )

        observation_list = self.client.get("/api/v1/anomalies/immediate-actions/")
        observation_ids = {item["id"] for item in observation_list.data["results"]}
        self.assertNotIn(str(anomaly.pk), observation_ids)

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
        due_date = timezone.localdate() + timedelta(days=7)

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
            },
            format="json",
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


    def test_admin_can_search_anomalies_by_area_and_status_not_reporter(self):
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
        Anomaly.objects.create(
            code=f"{year}9010",
            title="Anomalia registrada",
            description="Detalle",
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
        anomaly_b = Anomaly.objects.create(
            code=f"{year}9011",
            title="Anomalia de Carlos",
            description="Detalle",
            current_status=AnomalyStatus.IN_ANALYSIS,
            current_stage=AnomalyStage.CAUSE_ANALYSIS,
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

        response_reporter = self.client.get("/api/v1/anomalies/?search=Lucia")
        self.assertEqual(response_reporter.status_code, status.HTTP_200_OK)
        self.assertEqual(response_reporter.data["count"], 0)

        response_area = self.client.get("/api/v1/anomalies/?search=Area 1")
        self.assertEqual(response_area.status_code, status.HTTP_200_OK)
        self.assertEqual(response_area.data["count"], 2)

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
