from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.actions.models import ActionHistoryEvent, ActionItemHistory, ActionItemStatus
from apps.actions.selectors import my_action_items_queryset
from apps.actions.services import create_action_item, create_action_plan, transition_action_item
from apps.anomalies.models import Anomaly, AnomalyStage, AnomalyStatus
from apps.catalog.models import ActionType, AnomalyOrigin, AnomalyType, Area, Priority, Severity, Site
from apps.notifications.models import NotificationRecipient, NotificationTaskType, RecipientTaskStatus


class ActionWorkflowServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.assignee = User.objects.create_user(
            username="operario",
            email="operario@example.com",
            password="secret123",
        )
        execute_permission = Permission.objects.get(
            content_type__app_label="actions",
            codename="execute_action",
        )
        self.assignee.user_permissions.add(execute_permission)

        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.anomaly_type = AnomalyType.objects.create(code="TIPO", name="Tipo")
        self.anomaly_origin = AnomalyOrigin.objects.create(code="ORIG", name="Origen")
        self.severity = Severity.objects.create(code="ALTA", name="Alta")
        self.priority = Priority.objects.create(code="P1", name="Prioridad 1")
        self.action_type = ActionType.objects.get(code="CORR")

        now = timezone.now()
        self.anomaly = Anomaly.objects.create(
            code="ANO-S01-2026-000001",
            title="Desviacion de prueba",
            description="Descripcion",
            current_status=AnomalyStatus.IN_ANALYSIS,
            current_stage=AnomalyStage.CAUSE_ANALYSIS,
            site=self.site,
            area=self.area,
            reporter=self.admin,
            anomaly_type=self.anomaly_type,
            anomaly_origin=self.anomaly_origin,
            severity=self.severity,
            priority=self.priority,
            detected_at=now,
            last_transition_at=now,
            created_by=self.admin,
            updated_by=self.admin,
        )

    def test_create_and_transition_action_item_updates_history_and_task_queue(self):
        action_plan = create_action_plan(
            anomaly=self.anomaly,
            user=self.admin,
            data={"owner": self.admin},
            request_id="req-plan",
        )

        item = create_action_item(
            action_plan=action_plan,
            user=self.admin,
            data={
                "action_type": self.action_type,
                "assigned_to": self.assignee,
                "title": "Actualizar instructivo",
                "description": "Capacitar al personal y actualizar documento.",
                "due_date": timezone.localdate() + timedelta(days=3),
                "expected_evidence": "Registro de capacitacion",
                "sequence": 1,
            },
            request_id="req-item",
        )

        self.assertTrue(item.code.startswith("ACT-ANO-S01-2026-000001-01"))
        self.assertEqual(item.priority_id, self.priority.pk)
        self.assertEqual(
            ActionItemHistory.objects.filter(action_item=item, event_type=ActionHistoryEvent.CREATED).count(),
            1,
        )

        recipient = NotificationRecipient.objects.get(
            notification__source_type="actions.actionitem",
            notification__source_id=item.pk,
            user=self.assignee,
        )
        self.assertTrue(recipient.notification.is_task)
        self.assertEqual(recipient.notification.task_type, NotificationTaskType.ACTION_ASSIGNMENT)
        self.assertEqual(recipient.task_status, RecipientTaskStatus.PENDING)
        self.assertTrue(my_action_items_queryset(self.assignee, pending_only=True).filter(pk=item.pk).exists())

        transition_action_item(
            action_item=item,
            user=self.assignee,
            target_status=ActionItemStatus.IN_PROGRESS,
            comment="Se inicia la ejecucion.",
            request_id="req-progress",
        )
        recipient.refresh_from_db()
        self.assertEqual(recipient.task_status, RecipientTaskStatus.IN_PROGRESS)

        transition_action_item(
            action_item=item,
            user=self.assignee,
            target_status=ActionItemStatus.COMPLETED,
            comment="Se completa la accion.",
            closure_comment="Ejecucion terminada.",
            request_id="req-complete",
        )
        recipient.refresh_from_db()
        self.assertEqual(recipient.task_status, RecipientTaskStatus.COMPLETED)
        self.assertFalse(my_action_items_queryset(self.assignee, pending_only=True).filter(pk=item.pk).exists())
