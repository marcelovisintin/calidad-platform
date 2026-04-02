from rest_framework import status
from rest_framework.test import APITestCase


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
