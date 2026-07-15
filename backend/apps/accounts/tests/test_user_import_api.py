from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.api.serializers import UserWriteSerializer
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
        return SimpleUploadedFile(
            "usuarios.csv", content.encode("utf-8"), content_type="text/csv"
        )

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
        initial_password = response.data["items"][0]["initial_password"]
        self.assertGreaterEqual(len(initial_password), 16)
        self.assertNotEqual(initial_password, "12345678")
        self.assertTrue(user.check_password(initial_password))

    def test_manual_user_creation_returns_generated_temporary_password_once(self):
        response = self.client.post(
            "/api/v1/accounts/users/",
            {
                "username": "new.operator",
                "email": "new.operator@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        initial_password = response.data["initial_password"]
        self.assertGreaterEqual(len(initial_password), 16)
        self.assertNotEqual(initial_password, "12345678")
        user = User.objects.get(username="new.operator")
        self.assertTrue(user.check_password(initial_password))
        self.assertTrue(user.must_change_password)
        detail_response = self.client.get(f"/api/v1/accounts/users/{user.pk}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("initial_password", detail_response.data)

    def test_manual_user_creation_rejects_common_temporary_password(self):
        response = self.client.post(
            "/api/v1/accounts/users/",
            {
                "username": "unsafe.operator",
                "email": "unsafe.operator@example.com",
                "password": "12345678",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_user_photo_rejects_unsupported_format(self):
        serializer = UserWriteSerializer(
            data={
                "username": "unsafe.photo",
                "email": "unsafe.photo@example.com",
                "photo": SimpleUploadedFile(
                    "profile.svg",
                    b"<svg></svg>",
                    content_type="image/svg+xml",
                ),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("photo", serializer.errors)
