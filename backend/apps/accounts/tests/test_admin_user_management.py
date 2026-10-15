from django.test import TestCase

from apps.accounts.models import Role, User
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership


class AdminUserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="root@t.invalid", password="pw", full_name="Root", phone_number="+263770010001", national_id="r1"
        )
        self.client.force_login(self.admin)

    def _add(self, role_code, n):
        role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
        return self.client.post(
            "/admin/accounts/user/add/",
            {
                "email": f"new{n}@t.invalid",
                "full_name": "New User",
                "phone_number": f"+26377002{n:04d}",
                "national_id": f"n{n}",
                "address": "",
                "role": str(role.pk),
                "verification_status": "resident",
                "is_active": "on",
                "password1": "Sup3r-secret-pw!",
                "password2": "Sup3r-secret-pw!",
                "neighborhood_memberships-TOTAL_FORMS": "0",
                "neighborhood_memberships-INITIAL_FORMS": "0",
                "neighborhood_memberships-MIN_NUM_FORMS": "0",
                "neighborhood_memberships-MAX_NUM_FORMS": "1000",
            },
        )

    def test_add_user_in_every_role(self):
        for i, code in enumerate(Role.Code.values, start=1):
            self.assertEqual(self._add(code, i).status_code, 302, code)
            user = User.objects.get(email=f"new{i}@t.invalid")
            self.assertEqual(user.role.code, code)
            self.assertEqual(user.verification_status, User.VerificationStatus.APPROVED)
            self.assertIsNotNone(user.otp_verified_at)
            self.assertEqual(user.is_staff, code == Role.Code.SYSTEM_ADMIN)

    def test_bulk_role_change_and_deactivate(self):
        user = User.objects.create_user(
            email="u@t.invalid", password="x", full_name="U", phone_number="+263770030001", national_id="u1"
        )
        r = self.client.post(
            "/admin/accounts/user/",
            {"action": "set_role_coordinator", "_selected_action": [str(user.pk)]},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.role.code, Role.Code.COORDINATOR)
        self.client.post(
            "/admin/accounts/user/",
            {"action": "deactivate_accounts", "_selected_action": [str(user.pk), str(self.admin.pk)]},
        )
        user.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(self.admin.is_active)  # never locks itself out

    def test_change_page_shows_memberships(self):
        hood = Neighborhood.objects.create(name="Test", code="TST")
        NeighborhoodMembership.objects.create(user=self.admin, neighborhood=hood)
        r = self.client.get(f"/admin/accounts/user/{self.admin.pk}/change/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "neighborhood_memberships-0-neighborhood")
