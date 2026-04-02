from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.anomalies.models import Anomaly, AnomalyParticipant, AnomalyStage, AnomalyStatus, ParticipantRole
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
        self.assertIn("Criterio de clasificacion aplicado", patch_response.data["classification"]["summary"])
        self.assertIn(self.severity.name, patch_response.data["classification"]["summary"])

        participant_exists = AnomalyParticipant.objects.filter(
            anomaly_id=anomaly_id,
            user=self.user,
            role=ParticipantRole.VERIFIER,
        ).exists()
        self.assertTrue(participant_exists)

