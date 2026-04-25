from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.anomalies.models import Anomaly, AnomalyCodeReservation, AnomalyParticipant, AnomalyStage, AnomalyStatus, ParticipantRole
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site


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
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

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
        self.assertRegex(response.data["code"], rf"^{timezone.localdate().year}\d{{4}}$")

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

    def test_create_anomaly_allows_missing_severity(self):
        payload = self._build_payload("003", include_severity=False)

        response = self.client.post("/api/v1/anomalies/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["severity"])

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


    def test_admin_can_search_anomalies_by_reporter_user_data(self):
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
        anomaly_a = Anomaly.objects.create(
            code=f"{year}9010",
            title="Anomalia de Lucia",
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
        Anomaly.objects.create(
            code=f"{year}9011",
            title="Anomalia de Carlos",
            description="Detalle",
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

        response_username = self.client.get("/api/v1/anomalies/?search=usuario_busqueda")
        self.assertEqual(response_username.status_code, status.HTTP_200_OK)
        self.assertEqual(response_username.data["count"], 1)
        self.assertEqual(response_username.data["results"][0]["id"], str(anomaly_a.pk))

        response_name = self.client.get("/api/v1/anomalies/?search=Lucia")
        self.assertEqual(response_name.status_code, status.HTTP_200_OK)
        self.assertEqual(response_name.data["count"], 1)
        self.assertEqual(response_name.data["results"][0]["id"], str(anomaly_a.pk))

        response_email = self.client.get("/api/v1/anomalies/?search=busqueda@example.com")
        self.assertEqual(response_email.status_code, status.HTTP_200_OK)
        self.assertEqual(response_email.data["count"], 1)
        self.assertEqual(response_email.data["results"][0]["id"], str(anomaly_a.pk))

    def test_admin_classification_registers_verification_and_classification_records(self):
        payload = self._build_payload("005", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]
        patch_response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity.pk)},
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["current_stage"], AnomalyStage.CLASSIFICATION)
        self.assertEqual(patch_response.data["current_status"], AnomalyStatus.IN_EVALUATION)

        self.assertIsNotNone(patch_response.data["initial_verification"])
        self.assertIsNotNone(patch_response.data["classification"])
        self.assertIn("Criterio de REVICION DE HALLAZGOS aplicado", patch_response.data["classification"]["summary"])
        self.assertIn(self.severity.name, patch_response.data["classification"]["summary"])

        participant_exists = AnomalyParticipant.objects.filter(
            anomaly_id=anomaly_id,
            user=self.user,
            role=ParticipantRole.VERIFIER,
        ).exists()
        self.assertTrue(participant_exists)






    def test_classification_only_allows_one_change_without_unlock(self):
        payload = self._build_payload("007", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]

        first_classification = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity.pk)},
            format="json",
        )
        self.assertEqual(first_classification.status_code, status.HTTP_200_OK)

        second_classification = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity_alt.pk)},
            format="json",
        )
        self.assertEqual(second_classification.status_code, status.HTTP_200_OK)
        self.assertEqual(second_classification.data["classification_change_count"], 1)
        self.assertFalse(second_classification.data["can_modify_classification"])
        self.assertTrue(second_classification.data["can_unlock_classification"])

        blocked_change = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity_extra.pk)},
            format="json",
        )
        self.assertEqual(blocked_change.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No se puede modificar la REVICION DE HALLAZGOS", str(blocked_change.data))

        unlock_response = self.client.post(f"/api/v1/anomalies/{anomaly_id}/classification/unlock/", {}, format="json")
        self.assertEqual(unlock_response.status_code, status.HTTP_200_OK)
        self.assertTrue(unlock_response.data["can_modify_classification"])

        unlocked_change = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity_extra.pk)},
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
        self.assertIn("No se puede modificar la REVICION DE HALLAZGOS", str(unlock_response.data))


    def test_create_treatment_moves_anomaly_to_treatment_created_and_blocks_classification(self):
        payload = self._build_payload("009", include_severity=False)
        create_response = self.client.post("/api/v1/anomalies/", payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        anomaly_id = create_response.data["id"]
        classify_response = self.client.patch(
            f"/api/v1/anomalies/{anomaly_id}/",
            {"severity": str(self.severity.pk)},
            format="json",
        )
        self.assertEqual(classify_response.status_code, status.HTTP_200_OK)

        treatment_response = self.client.post(
            "/api/v1/actions/treatments/",
            {"primary_anomaly": anomaly_id},
            format="json",
        )
        self.assertEqual(treatment_response.status_code, status.HTTP_201_CREATED)

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
