from django.apps import apps as django_apps
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


class ScopedRolePermissionBackend(ModelBackend):
    def get_role_permissions(self, user_obj, obj=None):
        if not user_obj or user_obj.is_anonymous or not user_obj.is_active:
            return set()

        cache_name = "_role_permissions_cache"
        if hasattr(user_obj, cache_name):
            return getattr(user_obj, cache_name)

        db_alias = user_obj._state.db or "default"
        permissions = Permission.objects.using(db_alias).filter(
            business_roles__is_active=True,
            business_roles__user_scopes__user=user_obj,
        ).values_list("content_type__app_label", "codename").distinct()

        resolved = {f"{app_label}.{codename}" for app_label, codename in permissions}
        setattr(user_obj, cache_name, resolved)
        return resolved

    def get_all_permissions(self, user_obj, obj=None):
        return super().get_all_permissions(user_obj, obj=obj) | self.get_role_permissions(user_obj, obj=obj)
