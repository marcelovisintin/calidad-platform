from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User


class PasswordRotationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="temporary_user",
            email="temporary_user@example.com",
            password="Temporary1!",
            must_change_password=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_temporary_password_only_allows_session_and_password_change_endpoints(self):
        self.assertEqual(self.client.get("/api/v1/accounts/me/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get("/api/v1/anomalies/workflow-metadata/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/api/v1/actions/dashboard-summary/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        change_response = self.client.post(
            "/api/v1/accounts/change-password/",
            {
                "current_password": "Temporary1!",
                "new_password": "SaferPassword#2026",
                "confirm_password": "SaferPassword#2026",
            },
            format="json",
        )

        self.assertEqual(change_response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertEqual(
            self.client.get("/api/v1/actions/dashboard-summary/").status_code,
            status.HTTP_200_OK,
        )
