from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.actions.models import Treatment, TreatmentTask
from apps.anomalies.models import Anomaly, ObservationAction
from common.deadlines import is_overdue


class DeadlineTests(SimpleTestCase):
    def test_date_deadline_includes_its_entire_day(self):
        today = timezone.localdate()
        self.assertTrue(is_overdue(today - timedelta(days=1), "pending"))
        self.assertFalse(is_overdue(today, "pending"))
        self.assertFalse(is_overdue(today + timedelta(days=1), "pending"))
        self.assertFalse(is_overdue(None, "pending"))

    def test_terminal_elements_are_never_overdue(self):
        for status in ("completed", "closed", "cancelled", "effective", "resolved"):
            with self.subTest(status=status):
                self.assertFalse(is_overdue(date(2000, 1, 1), status))

    def test_treatment_deadline_and_verification_deadline_are_independent(self):
        treatment = Treatment(status="in_progress", deadline=date(2000, 1, 1),
                              effectiveness_evaluation_date=timezone.localdate())
        self.assertTrue(treatment.is_overdue)
        self.assertFalse(treatment.effectiveness_is_overdue)
        treatment.deadline = timezone.localdate()
        treatment.effectiveness_evaluation_date = date(2000, 1, 1)
        self.assertFalse(treatment.is_overdue)
        self.assertTrue(treatment.effectiveness_is_overdue)
        treatment.effectiveness_validated_at = timezone.now()
        self.assertFalse(treatment.effectiveness_is_overdue)

    def test_closed_treatment_suppresses_pending_child_warning(self):
        task = TreatmentTask(status="pending", execution_date=date(2000, 1, 1),
                             treatment=Treatment(status="completed"))
        self.assertFalse(task.is_overdue)

    def test_closed_observation_suppresses_pending_child_warning(self):
        action = ObservationAction(status="pending", estimated_completion_date=date(2000, 1, 1),
                                   anomaly=Anomaly(current_status="closed"))
        self.assertFalse(action.is_overdue)

    def test_observation_moves_deadline_from_action_to_verification(self):
        today = timezone.localdate()
        action = SimpleNamespace(status="pending", estimated_completion_date=today - timedelta(days=1),
                                 effectiveness_due_date=today + timedelta(days=2))
        observation = SimpleNamespace(action_date=date(2000, 1, 1), action_completed_at=None,
                                      effectiveness_verified_at=None, effectiveness_due_at=None)
        anomaly = SimpleNamespace(treatment_links=Mock(), observation_actions=Mock(),
                                  immediate_action=observation, observation_resolution_path="OBSERVATION")
        anomaly.treatment_links.all.return_value = []
        anomaly.observation_actions.all.return_value = [action]
        self.assertEqual(Anomaly.deadline.fget(anomaly), action.estimated_completion_date)
        action.status = "completed"
        self.assertEqual(Anomaly.deadline.fget(anomaly), action.effectiveness_due_date)
        observation.effectiveness_verified_at = timezone.now()
        self.assertIsNone(Anomaly.deadline.fget(anomaly))

    def test_datetime_uses_business_timezone_at_midnight(self):
        with patch("common.deadlines.timezone.localdate", return_value=date(2026, 9, 9)):
            self.assertTrue(is_overdue(timezone.datetime(2026, 9, 9, 1, tzinfo=timezone.get_fixed_timezone(0)), "pending"))
