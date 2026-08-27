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
