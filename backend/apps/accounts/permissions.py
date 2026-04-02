from rest_framework.permissions import BasePermission

from apps.accounts.constants import (
    PERMISSION_ADD_USER,
    PERMISSION_ANALYZE_ANOMALY,
    PERMISSION_ASSIGN_ACTION,
    PERMISSION_CANCEL_ANOMALY,
    PERMISSION_CHANGE_USER,
    PERMISSION_CLASSIFY_ANOMALY,
    PERMISSION_CLOSE_ANOMALY,
    PERMISSION_CREATE_ANOMALY,
    PERMISSION_DELETE_USER,
    PERMISSION_EDIT_ANOMALY,
    PERMISSION_EXECUTE_ACTION,
    PERMISSION_REOPEN_ANOMALY,
    PERMISSION_VERIFY_ACTION_EFFECTIVENESS,
    PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
    PERMISSION_VIEW_ALL_ANOMALY,
    PERMISSION_VIEW_AUDIT,
    PERMISSION_VIEW_SECTOR_ANOMALY,
    PERMISSION_VIEW_USER,
)
from apps.accounts.services.authorization import can_access_area


class HasBusinessPermission(BasePermission):
    required_permission = ""
    message = "No tiene permisos suficientes para ejecutar esta operacion."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and self.required_permission
            and user.has_perm(self.required_permission)
        )


class CanListUsers(HasBusinessPermission):
    required_permission = PERMISSION_VIEW_USER
    message = "No tiene permisos para consultar usuarios."


class CanCreateUsers(HasBusinessPermission):
    required_permission = PERMISSION_ADD_USER
    message = "No tiene permisos para crear usuarios."


class CanEditUsers(HasBusinessPermission):
    required_permission = PERMISSION_CHANGE_USER
    message = "No tiene permisos para editar usuarios."


class CanDeleteUsers(HasBusinessPermission):
    required_permission = PERMISSION_DELETE_USER
    message = "No tiene permisos para eliminar usuarios."


class CanViewAuditTrail(HasBusinessPermission):
    required_permission = PERMISSION_VIEW_AUDIT
    message = "No tiene permisos para consultar la auditoria transversal."


class CanCreateAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_CREATE_ANOMALY

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if user.is_superuser:
            return True
        if getattr(user, "access_level", "") == "usuario_activo":
            return True
        return bool(self.required_permission and user.has_perm(self.required_permission))


class CanEditAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_EDIT_ANOMALY


class CanClassifyAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_CLASSIFY_ANOMALY


class CanAnalyzeAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_ANALYZE_ANOMALY


class CanAssignAction(HasBusinessPermission):
    required_permission = PERMISSION_ASSIGN_ACTION


class CanExecuteAction(HasBusinessPermission):
    required_permission = PERMISSION_EXECUTE_ACTION


class CanVerifyAnomalyEffectiveness(HasBusinessPermission):
    required_permission = PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY


class CanVerifyActionEffectiveness(HasBusinessPermission):
    required_permission = PERMISSION_VERIFY_ACTION_EFFECTIVENESS


class CanCloseAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_CLOSE_ANOMALY


class CanCancelAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_CANCEL_ANOMALY


class CanReopenAnomaly(HasBusinessPermission):
    required_permission = PERMISSION_REOPEN_ANOMALY


class CanViewAllAnomalies(HasBusinessPermission):
    required_permission = PERMISSION_VIEW_ALL_ANOMALY


class CanViewSectorAnomalies(HasBusinessPermission):
    required_permission = PERMISSION_VIEW_SECTOR_ANOMALY


class HasSectorScope(BasePermission):
    message = "No tiene alcance sobre el sector solicitado."

    def has_object_permission(self, request, view, obj) -> bool:
        return can_access_area(
            request.user,
            area_id=getattr(obj, "area_id", None),
            site_id=getattr(obj, "site_id", None),
        )
