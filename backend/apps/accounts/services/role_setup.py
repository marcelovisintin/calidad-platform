from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from apps.accounts.constants import PERMISSION_DEFINITIONS
from apps.accounts.models import User
from apps.actions.models import ActionItem, ActionPlan
from apps.anomalies.models import Anomaly
from apps.audit.models import AuditEvent

MODEL_MAP = {
    "accounts.user": User,
    "anomalies.anomaly": Anomaly,
    "actions.actionplan": ActionPlan,
    "actions.actionitem": ActionItem,
    "audit.auditevent": AuditEvent,
}



def ensure_permission(permission_key: str) -> Permission:
    definition = PERMISSION_DEFINITIONS[permission_key]
    model_key = f"{definition['app_label']}.{definition['model']}"
    model_class = MODEL_MAP[model_key]
    content_type = ContentType.objects.get_for_model(model_class)
    permission, created = Permission.objects.get_or_create(
        content_type=content_type,
        codename=definition["codename"],
        defaults={"name": definition["name"]},
    )
    if not created and permission.name != definition["name"]:
        permission.name = definition["name"]
        permission.save(update_fields=["name"])
    return permission



def ensure_required_permissions() -> dict[str, Permission]:
    return {key: ensure_permission(key) for key in PERMISSION_DEFINITIONS}


def sync_roles_and_permissions() -> None:
    ensure_required_permissions()
