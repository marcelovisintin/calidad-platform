from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.constants import (
    PERMISSION_CREATE_ANOMALY,
    PERMISSION_VIEW_ACTION_ITEM,
    USER_SCOPE_OPTIONS,
)
from apps.accounts.models import Role, User
from apps.accounts.services.role_setup import ensure_required_permissions
from apps.catalog.models import Area, Site


class UserAccessProfileApiTests(APITestCase):
    def setUp(self):
        ensure_required_permissions()
        self.admin = User.objects.create_superuser(
            username="admin_scopes",
            email="admin_scopes@example.com",
            password="secret123",
        )
        self.site = Site.objects.create(code="S01", name="Sitio 1")
        self.area = Area.objects.create(site=self.site, code="A01", name="Area 1")
        self.role = Role.objects.create(code="OPER_TEST", name="Operativo test")
        self.role.permissions.add(
            *[
                permission
                for permission in ensure_required_permissions().values()
                if f"{permission.content_type.app_label}.{permission.codename}" == PERMISSION_VIEW_ACTION_ITEM
            ]
        )
        self.target_user = User.objects.create_user(
            username="mechi_scopes",
            email="mechi_scopes@example.com",
            password="secret123",
            primary_sector=self.area,
        )
        self.client.force_authenticate(user=self.admin)

    def test_access_profile_updates_level_role_and_manual_scope_permissions(self):
        response = self.client.patch(
            f"/api/v1/accounts/users/{self.target_user.pk}/access-profile/",
            {
                "access_level": "mando_medio_activo",
                "role": str(self.role.pk),
                "manual_scope_keys": ["new_anomaly"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.access_level, "mando_medio_activo")
        self.assertEqual(response.data["role"]["id"], str(self.role.pk))
        self.assertEqual(response.data["manual_scope_keys"], ["new_anomaly"])
        self.assertIn(PERMISSION_CREATE_ANOMALY, response.data["effective_permissions"])
        self.assertIn(PERMISSION_VIEW_ACTION_ITEM, response.data["role_permissions"])

    def test_access_options_expose_expected_checklist_scopes(self):
        response = self.client.get("/api/v1/accounts/users/access-options/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_keys = {option["key"] for option in USER_SCOPE_OPTIONS}
        response_keys = {option["key"] for option in response.data["scope_options"]}
        self.assertTrue(expected_keys.issubset(response_keys))
