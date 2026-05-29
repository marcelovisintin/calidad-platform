from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.services.role_setup import ensure_required_permissions


class UserImportApiTests(APITestCase):
    def setUp(self):
        ensure_required_permissions()
        self.admin = User.objects.create_superuser(
            username="admin_import",
            email="admin_import@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=self.admin)

    def _csv_file(self, content: str):
        return SimpleUploadedFile("usuarios.csv", content.encode("utf-8"), content_type="text/csv")

    def test_preview_accepts_optional_legajo_and_phone(self):
        csv_content = (
            "legajo,nombre,apellido,e-mail,usuario,celular\n"
            ",Ana,Perez,ana@example.com,ana.perez,\n"
        )

        response = self.client.post(
            "/api/v1/accounts/users/import/preview/",
            {"file": self._csv_file(csv_content), "mode": "upsert"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["total"], 1)
        self.assertEqual(response.data["summary"]["errors"], 0)
        self.assertEqual(response.data["items"][0]["status"], "create")

    def test_preview_validates_duplicate_email_and_username(self):
        csv_content = (
            "legajo,nombre,apellido,email,usuario,celular\n"
            "1001,Ana,Perez,ana@example.com,ana,\n"
            "1002,Ana2,Perez2,ana@example.com,ana,\n"
        )

        response = self.client.post(
            "/api/v1/accounts/users/import/preview/",
            {"file": self._csv_file(csv_content), "mode": "upsert"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["errors"], 2)
        self.assertEqual(response.data["summary"]["duplicate_emails"], 1)
        self.assertEqual(response.data["summary"]["duplicate_usernames"], 1)

    def test_confirm_creates_valid_user_with_basic_fields(self):
        csv_content = (
            "legajo,nombre,apellido,email,usuario,celular\n"
            "1002,Bruno,Gomez,bruno@example.com,bruno.gomez,+54 9 11 1234-5678\n"
        )

        response = self.client.post(
            "/api/v1/accounts/users/import/confirm/",
            {"file": self._csv_file(csv_content), "mode": "upsert"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["created"], 1)
        user = User.objects.get(email="bruno@example.com")
        self.assertEqual(user.username, "bruno.gomez")
        self.assertEqual(user.employee_code, "1002")
        self.assertEqual(user.first_name, "Bruno")
        self.assertEqual(user.last_name, "Gomez")
        self.assertEqual(user.phone, "+54 9 11 1234-5678")
