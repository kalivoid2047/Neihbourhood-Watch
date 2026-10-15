from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User


def make(email, n, **kw):
    return User.objects.create_user(
        email=email, password="x", full_name="U", phone_number=f"+26377000{n:04d}", national_id=f"id{n}", **kw
    )


class DefaultRoleTests(TestCase):
    def test_new_accounts_are_residents(self):
        self.assertEqual(make("a@t.invalid", 1).role.code, Role.Code.RESIDENT)

    def test_existing_role_is_kept(self):
        cap = Role.objects.create(code=Role.Code.BLOCK_CAPTAIN, name="Block Captain")
        self.assertEqual(make("b@t.invalid", 2, role=cap).role.code, Role.Code.BLOCK_CAPTAIN)


class ApplyBlockCaptainTests(TestCase):
    def setUp(self):
        self.user = make("r@t.invalid", 3)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = "/api/users/me/apply-block-captain"

    def test_resident_can_apply_once(self):
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json()["block_captain_applied_at"])
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_non_resident_cannot_apply(self):
        self.user.role = Role.objects.create(code=Role.Code.COORDINATOR, name="Coordinator")
        self.user.save()
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_admin_action_promotes(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage

        self.client.post(self.url)
        model_admin = admin.site._registry[User]
        req = RequestFactory().post("/")
        req.session = {}
        req._messages = FallbackStorage(req)
        model_admin.approve_block_captain(req, User.objects.filter(pk=self.user.pk))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role.code, Role.Code.BLOCK_CAPTAIN)
        self.assertIsNone(self.user.block_captain_applied_at)
