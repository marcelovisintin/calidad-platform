from rest_framework.permissions import BasePermission

from apps.accounts.services.access_policy import has_global_access


class CanViewIndicators(BasePermission):
    message = "Solo Administradores y Desarrolladores pueden consultar los indicadores globales."

    def has_permission(self, request, view) -> bool:
        return has_global_access(request.user)
