from rest_framework.permissions import BasePermission


class IsAuthenticatedAndActive(BasePermission):
    message = "Se requiere un usuario autenticado y activo."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
