from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.actions.models import TreatmentCodeSequence
from apps.anomalies.models import AnomalyCodeReservation
from apps.audit.models import AuditEvent
from apps.catalog.models import Area, Site
from apps.notifications.models import Notification, NotificationTemplate


class ClearOperationalDataCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quality-admin",
            email="quality-admin@example.local",
            password="Strong-test-password-2026",
        )
        self.site = Site.objects.create(code="S01", name="Planta")
        self.area = Area.objects.create(code="CAL", name="Calidad", site=self.site)
        NotificationTemplate.objects.create(
            code="test-template",
            subject_template="Prueba",
            body_template="Prueba",
        )
        Notification.objects.create(
            source_type="anomalies.anomaly",
            source_id=self.user.pk,
            title="Pendiente de prueba",
        )
        AuditEvent.objects.create(
            entity_type="anomalies.anomaly",
            entity_id=self.user.pk,
            action="test.created",
            actor=self.user,
        )
        AnomalyCodeReservation.objects.create(
            code="20260001",
            year=2026,
            sequence=1,
            reserved_by=self.user,
        )
        TreatmentCodeSequence.objects.create(year=2026, last_sequence=17)

    def test_default_mode_is_dry_run(self):
        call_command("clear_operational_data", stdout=StringIO())

        self.assertTrue(Notification.objects.exists())
        self.assertTrue(AuditEvent.objects.exists())
        self.assertTrue(AnomalyCodeReservation.objects.exists())
        self.assertTrue(TreatmentCodeSequence.objects.exists())

    def test_confirm_clears_activity_and_preserves_configuration(self):
        call_command("clear_operational_data", "--confirm", stdout=StringIO())

        self.assertFalse(Notification.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(AnomalyCodeReservation.objects.exists())
        self.assertFalse(TreatmentCodeSequence.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Site.objects.filter(pk=self.site.pk).exists())
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())
        self.assertTrue(
            NotificationTemplate.objects.filter(code="test-template").exists()
        )
