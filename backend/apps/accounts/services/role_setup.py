from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.accounts.constants import PERMISSION_DEFINITIONS, ROLE_DEFINITIONS, ROLE_PERMISSION_MATRIX
from apps.accounts.models import Role, User
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


@transaction.atomic
def sync_roles_and_permissions() -> None:
    resolved_permissions = ensure_required_permissions()

    for role_code, role_definition in ROLE_DEFINITIONS.items():
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={
                "name": role_definition["name"],
                "description": role_definition["description"],
            },
        )

        updates = []
        if role.name != role_definition["name"]:
            role.name = role_definition["name"]
            updates.append("name")
        if role.description != role_definition["description"]:
            role.description = role_definition["description"]
            updates.append("description")
        if not role.is_active:
            role.is_active = True
            updates.append("is_active")
        if updates:
            role.save(update_fields=updates)

        permission_objects = [resolved_permissions[key] for key in ROLE_PERMISSION_MATRIX[role_code]]
        role.permissions.set(permission_objects)
