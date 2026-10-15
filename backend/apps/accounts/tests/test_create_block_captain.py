from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import Role, User
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership


class CreateBlockCaptainCommandTests(TestCase):
    ARGS = dict(
        email="Captain@Test.invalid",
        password="Str0ng-pass!",
        full_name="Cap Tain",
        phone="+263771234567",
        national_id="63-123456-A-42",
    )

    def run_cmd(self, **kw):
        out = StringIO()
        call_command("create_block_captain", stdout=out, **{**self.ARGS, **kw})
        return out.getvalue()

    def test_create_then_rerun_promotes_without_error(self):
        self.assertIn("Created", self.run_cmd())
        self.assertIn("Promoted", self.run_cmd())
        user = User.objects.get(email__iexact="captain@test.invalid")
        self.assertEqual(user.role.code, Role.Code.BLOCK_CAPTAIN)

    def test_promote_existing_resident_and_join_neighborhood_twice(self):
        n = Neighborhood.objects.create(name="Test", code="TST")
        User.objects.create_user(
            email="r@test.invalid", password="x", full_name="R", phone_number="+263771111111", national_id="1"
        )
        for _ in range(2):
            call_command("create_block_captain", email="r@test.invalid", neighborhood="TST", stdout=StringIO())
        m = NeighborhoodMembership.objects.get(user__email="r@test.invalid", neighborhood=n)
        self.assertEqual(m.role, NeighborhoodMembership.Role.BLOCK_CAPTAIN)

    def test_bad_phone_is_a_clean_error(self):
        with self.assertRaisesMessage(CommandError, "phone_number"):
            self.run_cmd(phone="abc")

    def test_duplicate_phone_is_a_clean_error(self):
        User.objects.create_user(
            email="o@test.invalid", password="x", full_name="O", phone_number="+263771234567", national_id="2"
        )
        with self.assertRaises(CommandError):
            self.run_cmd()
