import uuid

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.catalog.models import Area, Site


class CatalogBootstrapApiTests(APITestCase):
    def test_catalog_bootstrap_exposes_minimum_runtime_catalogs(self):
        root_response = self.client.get("/api/v1/catalog/")
        self.assertEqual(root_response.status_code, status.HTTP_200_OK)
        self.assertEqual(root_response.data["bootstrap"], "/api/v1/catalog/bootstrap/")

        response = self.client.get("/api/v1/catalog/bootstrap/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(any(item["code"] == "001" for item in response.data["sites"]))
        self.assertTrue(any(item["name"] == "corte" for item in response.data["areas"]))
        self.assertTrue(any(item["code"] == "001" for item in response.data["anomalyTypes"]))
        self.assertTrue(any(item["code"] == "o01" for item in response.data["anomalyOrigins"]))
        self.assertTrue(any(item["code"] == "alta" for item in response.data["severities"]))
        self.assertTrue(any(item["code"] == "alta" for item in response.data["priorities"]))
        self.assertTrue(any(item["code"] == "CORR" for item in response.data["actionTypes"]))
        self.assertEqual(
            {item["code"] for item in response.data["orderTypes"]},
            {"OP", "OF", "OM"},
        )

    def test_management_directory_is_ordered_by_code(self):
        admin = User.objects.create_superuser(
            username="catalog_order_admin",
            email="catalog-order@example.com",
            password="test-password-123",
        )
        Site.objects.create(code="902", name="sort-code-test segundo", display_order=1)
        Site.objects.create(code="101", name="sort-code-test primero", display_order=99)
        self.client.force_authenticate(user=admin)

        response = self.client.get("/api/v1/catalog/sites/?q=sort-code-test&page_size=30")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["code"] for item in response.data["results"]],
            ["101", "902"],
        )

    def test_bootstrap_areas_used_by_operational_selectors_are_ordered_by_name(self):
        site = Site.objects.create(code="990", name="sort-bootstrap-site", display_order=1)
        Area.objects.create(site=site, code="101", name="sort-bootstrap Zulu", display_order=1)
        Area.objects.create(site=site, code="902", name="sort-bootstrap Alfa", display_order=99)

        response = self.client.get("/api/v1/catalog/bootstrap/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["code"] for item in response.data["areas"] if item["name"].startswith("sort-bootstrap")],
            ["902", "101"],
        )

    def test_delete_site_with_archived_user_scope_returns_controlled_error(self):
        admin = User.objects.create_superuser(
            username="catalog_delete_admin",
            email="catalog-delete-admin@example.com",
            password="test-password-123",
        )
        target_user = User.objects.create_user(
            username="catalog_scope_user",
            email="catalog-scope-user@example.com",
            password="test-password-123",
        )
        site = Site.objects.create(code="DEL-SITE", name="Sitio con alcance historico")
        now = timezone.now()
        role_id = uuid.uuid4()
        scope_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO accounts_role
                    (id, created_at, updated_at, row_version, code, name, description, is_active)
                VALUES (%s, %s, %s, 1, %s, %s, '', TRUE)
                """,
                [role_id, now, now, f"LEG-{role_id.hex[:8]}", "Rol historico"],
            )
            cursor.execute(
                """
                INSERT INTO accounts_userrolescope
                    (id, created_at, updated_at, row_version, area_id, created_by_id,
                     role_id, site_id, updated_by_id, user_id)
                VALUES (%s, %s, %s, 1, NULL, NULL, %s, %s, NULL, %s)
                """,
                [scope_id, now, now, role_id, site.pk, target_user.pk],
            )
        self.client.force_authenticate(user=admin)

        response = self.client.delete(f"/api/v1/catalog/sites/{site.pk}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("esta siendo utilizado", response.data["detail"])
        self.assertTrue(Site.objects.filter(pk=site.pk).exists())
