from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.anomalies.models import (
    AnalysisMethod,
    Anomaly,
    AnomalyCauseAnalysis,
    AnomalyClassification,
    AnomalyEffectivenessCheck,
    AnomalyInitialVerification,
    AnomalyLearning,
    AnomalyStage,
    AnomalyStatus,
)
from apps.anomalies.services.anomaly_service import transition_anomaly
from apps.catalog.models import AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site


class TransitionAnomalyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")

        detected_at = timezone.now()
        self.anomaly = Anomaly.objects.create(
            code="ANO-S01-2026-000001",
            title="Desviacion de prueba",
            description="Descripcion",
            current_status=AnomalyStatus.PENDING_VERIFICATION,
            current_stage=AnomalyStage.EFFECTIVENESS_VERIFICATION,
            site=self.site,
            area=self.area,
            reporter=self.user,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity,
            priority=self.priority,
            detected_at=detected_at,
            last_transition_at=detected_at,
            resolution_summary="Resolucion aplicada",
            result_summary="Resultados registrados",
            effectiveness_summary="Verificacion eficaz",
            created_by=self.user,
            updated_by=self.user,
        )

        AnomalyInitialVerification.objects.create(
            anomaly=self.anomaly,
            verified_by=self.user,
            verified_at=detected_at,
            created_by=self.user,
            updated_by=self.user,
        )
        AnomalyClassification.objects.create(
            anomaly=self.anomaly,
            classified_by=self.user,
            classified_at=detected_at,
            created_by=self.user,
            updated_by=self.user,
        )
        AnomalyCauseAnalysis.objects.create(
            anomaly=self.anomaly,
            analyzed_by=self.user,
            analyzed_at=detected_at,
            method_used=AnalysisMethod.FIVE_WHYS,
            root_cause="Causa raiz",
            created_by=self.user,
            updated_by=self.user,
        )
        AnomalyEffectivenessCheck.objects.create(
            anomaly=self.anomaly,
            verified_by=self.user,
            verified_at=detected_at,
            is_effective=True,
            evidence_summary="Sin recurrencia",
            comment="La accion fue eficaz",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_standardization_transition_preserves_closure_metadata(self):
        closed = transition_anomaly(
            anomaly=self.anomaly,
            user=self.user,
            target_stage=AnomalyStage.CLOSURE,
            comment="Cierre aprobado",
        )
        closed_at = closed.closed_at

        AnomalyLearning.objects.create(
            anomaly=closed,
            recorded_by=self.user,
            recorded_at=timezone.now(),
            standardization_actions="Estandar actualizado",
            lessons_learned="Leccion aprendida",
            document_changes="Cambio documental",
            shared_with="Calidad",
            created_by=self.user,
            updated_by=self.user,
        )

        standardized = transition_anomaly(
            anomaly=closed,
            user=self.user,
            target_stage=AnomalyStage.STANDARDIZATION_AND_LEARNING,
            comment="Aprendizaje registrado",
        )

        self.assertEqual(standardized.current_status, AnomalyStatus.CLOSED)
        self.assertEqual(standardized.current_stage, AnomalyStage.STANDARDIZATION_AND_LEARNING)
        self.assertEqual(standardized.closure_comment, "Cierre aprobado")
        self.assertEqual(standardized.closed_at, closed_at)
