from rest_framework.permissions import BasePermission


def has_active_api_session(user, *, allow_password_change_required: bool = False) -> bool:
    if not (user and user.is_authenticated and user.is_active):
        return False
    return allow_password_change_required or not getattr(user, "must_change_password", False)


class IsAuthenticatedAndActive(BasePermission):
    message = "Se requiere un usuario autenticado y activo."

    def has_permission(self, request, view) -> bool:
        user = request.user
        allow_password_change_required = bool(getattr(view, "allow_password_change_required", False))
        if not has_active_api_session(
            user,
            allow_password_change_required=allow_password_change_required,
        ):
            if user and user.is_authenticated and getattr(user, "must_change_password", False):
                self.message = "Debe cambiar la contrasena temporal antes de continuar."
            return False
        return True
