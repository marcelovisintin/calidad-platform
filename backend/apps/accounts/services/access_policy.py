from __future__ import annotations

from apps.accounts.models import User


GLOBAL_ACCESS_LEVELS = {
    User.AccessLevel.ADMINISTRADOR,
    User.AccessLevel.DESARROLLADOR,
}
MANAGEMENT_ACCESS_LEVELS = GLOBAL_ACCESS_LEVELS | {
    User.AccessLevel.MANDO_MEDIO_ACTIVO,
}


def is_active_user(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    )


def has_global_access(user) -> bool:
    return bool(
        is_active_user(user)
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "access_level", "") in GLOBAL_ACCESS_LEVELS
        )
    )


def is_management_user(user) -> bool:
    return bool(
        is_active_user(user)
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "access_level", "") in MANAGEMENT_ACCESS_LEVELS
        )
    )


def can_administer_platform(user) -> bool:
    return has_global_access(user)


def can_review_findings(user) -> bool:
    return has_global_access(user)


def can_create_anomaly(user) -> bool:
    return is_active_user(user)


def can_manage_assigned_process(user, responsible_id) -> bool:
    if has_global_access(user):
        return True
    return bool(
        is_management_user(user)
        and responsible_id
        and responsible_id == getattr(user, "id", None)
    )


def can_delegate_operational_work(user) -> bool:
    return is_management_user(user)


def can_execute_assignment(user, assigned_user_id) -> bool:
    return bool(
        is_active_user(user)
        and assigned_user_id
        and assigned_user_id == getattr(user, "id", None)
    )


def can_verify_assignment(user, assigned_user_id) -> bool:
    return can_execute_assignment(user, assigned_user_id)


def can_view_global_pending_control(user) -> bool:
    return has_global_access(user)


def is_assignable_process_manager(user) -> bool:
    return is_management_user(user)

