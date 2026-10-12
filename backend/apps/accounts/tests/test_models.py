from django.test import TestCase

from apps.accounts.models import Role, User


class UserModelTests(TestCase):
    def test_create_user_uses_email_identity(self):
        role = Role.objects.create(code=Role.Code.RESIDENT, name="Resident")

        user = User.objects.create_user(
            email="resident@example.com",
            password="secure-password",
            full_name="Resident One",
            phone_number="+263771234567",
            national_id="63-123456A47",
            role=role,
        )

        self.assertEqual(user.email, "resident@example.com")
        self.assertTrue(user.check_password("secure-password"))
        self.assertEqual(user.role, role)
        self.assertEqual(user.verification_status, User.VerificationStatus.RESIDENT)

