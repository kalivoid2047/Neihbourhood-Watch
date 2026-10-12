"""
Tests for Phase 8 — Neighborhood write API (join, leave, members, roles, create).

Covers:
  - GET /api/neighborhoods/ — public (unauthenticated)
  - POST /api/neighborhoods/ — admin-only create
  - POST /api/neighborhoods/{id}/join/ — join a neighborhood
  - DELETE /api/neighborhoods/{id}/leave/ — leave a neighborhood
  - GET /api/neighborhoods/{id}/members/ — coordinator-only member list
  - POST /api/neighborhoods/{id}/members/{user_id}/role/ — change member role
  - GET /api/neighborhoods/{id}/risk-summary/ — risk summary
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership


PASSWORD = "ZimSecurePass123!"


def make_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def make_user(email, role_code, *, national_id_suffix="01"):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name="Test User",
        phone_number=f"+26377{national_id_suffix}23456",
        national_id=f"63-12345{national_id_suffix}47",
        role=make_role(role_code),
    )


def make_neighborhood(name="Avondale", code=None):
    return Neighborhood.objects.create(
        name=name,
        code=code or name.lower().replace(" ", "-"),
        city="Harare",
        province="Harare",
        is_active=True,
    )


def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class NeighborhoodListPublicTests(TestCase):
    def setUp(self):
        make_neighborhood("Avondale")
        make_neighborhood("Borrowdale")

    def test_list_is_public(self):
        resp = APIClient().get("/api/neighborhoods/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["results"]), 2)

    def test_list_excludes_inactive(self):
        Neighborhood.objects.filter(name="Avondale").update(is_active=False)
        resp = APIClient().get("/api/neighborhoods/")
        names = [n["name"] for n in resp.data["results"]]
        self.assertNotIn("Avondale", names)


class NeighborhoodCreateTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", Role.Code.SYSTEM_ADMIN, national_id_suffix="99")
        self.resident = make_user("res@example.com", Role.Code.RESIDENT, national_id_suffix="11")

    def test_admin_can_create(self):
        resp = auth_client(self.admin).post("/api/neighborhoods/", {
            "name": "Highlands",
            "code": "highlands",
            "city": "Harare",
            "province": "Harare",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Highlands")

    def test_resident_cannot_create(self):
        resp = auth_client(self.resident).post("/api/neighborhoods/", {
            "name": "Highlands",
            "code": "highlands",
            "city": "Harare",
            "province": "Harare",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create(self):
        resp = APIClient().post("/api/neighborhoods/", {
            "name": "Highlands",
            "code": "highlands",
            "city": "Harare",
            "province": "Harare",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class NeighborhoodJoinLeaveTests(TestCase):
    def setUp(self):
        self.user = make_user("user@example.com", Role.Code.RESIDENT, national_id_suffix="22")
        self.neighborhood = make_neighborhood()
        self.client = auth_client(self.user)

    def test_join_neighborhood(self):
        resp = self.client.post(f"/api/neighborhoods/{self.neighborhood.pk}/join/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            NeighborhoodMembership.objects.filter(
                user=self.user, neighborhood=self.neighborhood, deleted_at__isnull=True
            ).exists()
        )

    def test_join_sets_primary_when_first(self):
        resp = self.client.post(f"/api/neighborhoods/{self.neighborhood.pk}/join/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["is_primary"])

    def test_join_duplicate_returns_400(self):
        self.client.post(f"/api/neighborhoods/{self.neighborhood.pk}/join/")
        resp = self.client.post(f"/api/neighborhoods/{self.neighborhood.pk}/join/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_leave_neighborhood(self):
        self.client.post(f"/api/neighborhoods/{self.neighborhood.pk}/join/")
        resp = self.client.delete(f"/api/neighborhoods/{self.neighborhood.pk}/leave/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            NeighborhoodMembership.objects.filter(
                user=self.user, neighborhood=self.neighborhood, deleted_at__isnull=True
            ).exists()
        )

    def test_leave_non_member_returns_400(self):
        resp = self.client.delete(f"/api/neighborhoods/{self.neighborhood.pk}/leave/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class NeighborhoodMembersTests(TestCase):
    def setUp(self):
        self.coordinator = make_user("coord@example.com", Role.Code.COORDINATOR, national_id_suffix="33")
        self.resident = make_user("res2@example.com", Role.Code.RESIDENT, national_id_suffix="44")
        self.neighborhood = make_neighborhood()
        NeighborhoodMembership.objects.create(
            user=self.resident, neighborhood=self.neighborhood, role="resident"
        )

    def test_coordinator_can_list_members(self):
        resp = auth_client(self.coordinator).get(f"/api/neighborhoods/{self.neighborhood.pk}/members/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_resident_cannot_list_members(self):
        resp = auth_client(self.resident).get(f"/api/neighborhoods/{self.neighborhood.pk}/members/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_coordinator_can_change_member_role(self):
        resp = auth_client(self.coordinator).post(
            f"/api/neighborhoods/{self.neighborhood.pk}/members/{self.resident.pk}/role/",
            {"role": "block_captain"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["role"], "block_captain")

    def test_change_role_for_nonmember_returns_400(self):
        other = make_user("other@example.com", Role.Code.RESIDENT, national_id_suffix="55")
        resp = auth_client(self.coordinator).post(
            f"/api/neighborhoods/{self.neighborhood.pk}/members/{other.pk}/role/",
            {"role": "block_captain"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
