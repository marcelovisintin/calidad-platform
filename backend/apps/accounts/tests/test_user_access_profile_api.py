from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.constants import (
    PERMISSION_CREATE_ANOMALY,
    USER_SCOPE_OPTIONS,
)
from apps.accounts.models import User
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
        self.target_user = User.objects.create_user(
            username="mechi_scopes",
            email="mechi_scopes@example.com",
            password="secret123",
            primary_sector=self.area,
        )
        self.client.force_authenticate(user=self.admin)

    def test_access_profile_updates_level_and_manual_scope_permissions(self):
        response = self.client.patch(
            f"/api/v1/accounts/users/{self.target_user.pk}/access-profile/",
            {
                "access_level": "mando_medio_activo",
                "manual_scope_keys": ["new_anomaly"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.access_level, "mando_medio_activo")
        self.assertEqual(response.data["manual_scope_keys"], ["new_anomaly"])
        self.assertIn(PERMISSION_CREATE_ANOMALY, response.data["effective_permissions"])

    def test_access_options_expose_expected_checklist_scopes(self):
        response = self.client.get("/api/v1/accounts/users/access-options/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_keys = {option["key"] for option in USER_SCOPE_OPTIONS}
        response_keys = {option["key"] for option in response.data["scope_options"]}
        self.assertTrue(expected_keys.issubset(response_keys))

    def test_administrator_access_level_can_list_users_without_sector_scope(self):
        administrator = User.objects.create_user(
            username="administrator_without_scope",
            email="administrator_without_scope@example.com",
            password="secret123",
            access_level=User.AccessLevel.ADMINISTRADOR,
        )
        self.client.force_authenticate(user=administrator)

        response = self.client.get("/api/v1/accounts/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(self.target_user.pk), returned_ids)
