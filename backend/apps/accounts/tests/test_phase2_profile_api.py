from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditLog


PASSWORD = "ZimSecurePass123!"


def create_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def create_user():
    return User.objects.create_user(
        email="profile@example.com",
        password=PASSWORD,
        full_name="Profile Resident",
        phone_number="+263772222222",
        national_id="63-222222A22",
        role=create_role(Role.Code.RESIDENT),
    )


class UserProfileAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()

    def authenticate(self):
        response = self.client.post(
            "/api/auth/login",
            {"email": self.user.email, "password": PASSWORD},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['tokens']['access']}")

    def test_retrieve_profile_requires_authentication(self):
        response = self.client.get("/api/users/me")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_profile_returns_current_user(self):
        self.authenticate()

        response = self.client.get("/api/users/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], self.user.email)
        self.assertEqual(response.json()["role"]["code"], Role.Code.RESIDENT)

    def test_update_profile_allows_profile_fields_and_keeps_role_read_only(self):
        self.authenticate()

        response = self.client.patch(
            "/api/users/me",
            {
                "full_name": "Updated Resident",
                "address": "Borrowdale, Harare",
                "phone_number": "+263772222223",
                "role": {"code": Role.Code.SYSTEM_ADMIN},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Updated Resident")
        self.assertEqual(self.user.address, "Borrowdale, Harare")
        self.assertEqual(self.user.phone_number, "+263772222223")
        self.assertEqual(self.user.role.code, Role.Code.RESIDENT)
        self.assertTrue(AuditLog.objects.filter(actor=self.user, action="profile_update").exists())

