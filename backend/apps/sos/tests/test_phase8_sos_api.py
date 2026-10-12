"""
Tests for Phase 8 — SOS API and Emergency Contact API.

Covers:
  - POST /api/me/emergency-contacts/ — create
  - GET  /api/me/emergency-contacts/ — list (own only)
  - PATCH /api/me/emergency-contacts/{id}/ — update
  - DELETE /api/me/emergency-contacts/{id}/ — soft delete
  - POST /api/sos/ — create alert, dispatches emergency contacts
  - POST /api/sos/{id}/ping/ — add location ping
  - POST /api/sos/{id}/resolve/ — resolve alert
  - POST /api/sos/{id}/cancel/ — cancel alert
  - GET  /api/sos/active/ — active alerts (coordinator/police only)
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import EmergencyContact, Role, User
from apps.sos.models import SOSAlert


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


def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


SOS_PAYLOAD = {
    "current_latitude": "-17.829320",
    "current_longitude": "31.052240",
    "address": "123 Test Street",
}


# ── Emergency Contact API ──────────────────────────────────────────────────────

class EmergencyContactTests(TestCase):
    def setUp(self):
        self.user = make_user("user@example.com", Role.Code.RESIDENT, national_id_suffix="10")
        self.other = make_user("other@example.com", Role.Code.RESIDENT, national_id_suffix="20")
        self.client = auth_client(self.user)

    def test_create_emergency_contact(self):
        resp = self.client.post("/api/me/emergency-contacts", {
            "name": "Alice Smith",
            "phone_number": "+263771234567",
            "relationship": "Sister",
            "priority": 1,
            "can_receive_sos": True,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Alice Smith")

    def test_list_own_contacts_only(self):
        EmergencyContact.objects.create(
            user=self.user, name="Mine", phone_number="+263771111111", priority=1
        )
        EmergencyContact.objects.create(
            user=self.other, name="Theirs", phone_number="+263772222222", priority=1
        )
        resp = self.client.get("/api/me/emergency-contacts")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["name"], "Mine")

    def test_patch_contact(self):
        contact = EmergencyContact.objects.create(
            user=self.user, name="Bob", phone_number="+263771111111", priority=1
        )
        resp = self.client.patch(
            f"/api/me/emergency-contacts/{contact.pk}",
            {"name": "Robert"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Robert")

    def test_delete_soft_deletes(self):
        contact = EmergencyContact.objects.create(
            user=self.user, name="Carol", phone_number="+263771111111", priority=1
        )
        resp = self.client.delete(f"/api/me/emergency-contacts/{contact.pk}")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        contact.refresh_from_db()
        self.assertIsNotNone(contact.deleted_at)

    def test_cannot_access_other_users_contact(self):
        contact = EmergencyContact.objects.create(
            user=self.other, name="Theirs", phone_number="+263772222222", priority=1
        )
        resp = self.client.get(f"/api/me/emergency-contacts/{contact.pk}")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_list(self):
        resp = APIClient().get("/api/me/emergency-contacts")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ── SOS Alert API ─────────────────────────────────────────────────────────────

class SOSAlertCreateTests(TestCase):
    def setUp(self):
        self.user = make_user("sos@example.com", Role.Code.RESIDENT, national_id_suffix="30")
        self.client = auth_client(self.user)

    @patch("apps.notifications.services.NotificationDispatchService.dispatch_sos_alert")
    def test_create_sos_alert(self, mock_dispatch):
        resp = self.client.post("/api/sos/", SOS_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], SOSAlert.Status.ACTIVE)
        mock_dispatch.assert_called_once()

    def test_create_missing_coordinates_returns_400(self):
        resp = self.client.post("/api/sos/", {"address": "somewhere"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_latitude_returns_400(self):
        resp = self.client.post("/api/sos/", {
            "current_latitude": "999",
            "current_longitude": "31.05",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_create(self):
        resp = APIClient().post("/api/sos/", SOS_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class SOSAlertLifecycleTests(TestCase):
    def setUp(self):
        from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership

        self.user = make_user("life@example.com", Role.Code.RESIDENT, national_id_suffix="40")
        self.coordinator = make_user("coord@example.com", Role.Code.COORDINATOR, national_id_suffix="41")
        self.client = auth_client(self.user)

        self.neighborhood = Neighborhood.objects.create(
            name="Test Neighborhood", code="test-neighborhood", city="Harare", province="Harare",
        )
        NeighborhoodMembership.objects.create(user=self.user, neighborhood=self.neighborhood)
        NeighborhoodMembership.objects.create(
            user=self.coordinator, neighborhood=self.neighborhood,
            role=NeighborhoodMembership.Role.COORDINATOR,
        )

    def _create_alert(self):
        from django.utils import timezone
        return SOSAlert.objects.create(
            user=self.user,
            neighborhood=self.neighborhood,
            status=SOSAlert.Status.ACTIVE,
            started_at=timezone.now(),
            current_latitude="-17.8",
            current_longitude="31.0",
        )

    def test_add_location_ping(self):
        from django.utils import timezone
        alert = self._create_alert()
        resp = self.client.post(f"/api/sos/{alert.pk}/ping/", {
            "latitude": "-17.83",
            "longitude": "31.05",
            "captured_at": timezone.now().isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data["latitude"]), -17.83)

    def test_resolve_alert(self):
        alert = self._create_alert()
        resp = self.client.post(f"/api/sos/{alert.pk}/resolve/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], SOSAlert.Status.RESOLVED)
        alert.refresh_from_db()
        self.assertIsNotNone(alert.ended_at)

    def test_cancel_alert(self):
        alert = self._create_alert()
        resp = self.client.post(f"/api/sos/{alert.pk}/cancel/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], SOSAlert.Status.CANCELLED)

    def test_cannot_resolve_already_closed_alert(self):
        from django.utils import timezone
        alert = self._create_alert()
        alert.status = SOSAlert.Status.RESOLVED
        alert.ended_at = timezone.now()
        alert.save()
        resp = self.client.post(f"/api/sos/{alert.pk}/resolve/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_active_alerts_visible_to_coordinator(self):
        self._create_alert()
        resp = auth_client(self.coordinator).get("/api/sos/active/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_resident_cannot_view_active_alerts(self):
        resp = self.client.get("/api/sos/active/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_user_cannot_ping_alert(self):
        # Non-owner cannot see (let alone ping) another user's alert.
        # The viewset obscures existence as 404 rather than leaking it as 403.
        from django.utils import timezone
        alert = self._create_alert()
        other = make_user("other2@example.com", Role.Code.RESIDENT, national_id_suffix="42")
        resp = auth_client(other).post(f"/api/sos/{alert.pk}/ping/", {
            "latitude": "-17.83",
            "longitude": "31.05",
            "captured_at": timezone.now().isoformat(),
        }, format="json")
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))


class SOSNeighborhoodAssignmentTests(TestCase):
    """POST /api/sos/ must attach a neighborhood so scoped responders can see it."""

    def setUp(self):
        from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership

        self.resident = make_user("assign@example.com", Role.Code.RESIDENT, national_id_suffix="50")
        self.coordinator = make_user("assign-coord@example.com", Role.Code.COORDINATOR, national_id_suffix="51")
        self.hood = Neighborhood.objects.create(
            name="Avondale", code="avondale", city="Harare", province="Harare",
            centroid_latitude="-17.800000", centroid_longitude="31.033000", alert_radius_m=3000,
        )
        self.other_hood = Neighborhood.objects.create(
            name="Bulawayo CBD", code="byo-cbd", city="Bulawayo", province="Bulawayo",
            centroid_latitude="-20.150000", centroid_longitude="28.580000", alert_radius_m=3000,
        )
        NeighborhoodMembership.objects.create(
            user=self.coordinator, neighborhood=self.hood, role=NeighborhoodMembership.Role.COORDINATOR,
        )
        self.NeighborhoodMembership = NeighborhoodMembership

    @patch("apps.notifications.services.NotificationDispatchService.dispatch_sos_alert")
    def test_uses_primary_membership(self, _dispatch):
        self.NeighborhoodMembership.objects.create(user=self.resident, neighborhood=self.hood, is_primary=True)
        resp = auth_client(self.resident).post("/api/sos/", SOS_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(resp.data["neighborhood"]), str(self.hood.pk))

    @patch("apps.notifications.services.NotificationDispatchService.dispatch_sos_alert")
    def test_falls_back_to_nearest_zone_when_no_membership(self, _dispatch):
        resp = auth_client(self.resident).post(
            "/api/sos/",
            {"current_latitude": "-17.801000", "current_longitude": "31.034000"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(resp.data["neighborhood"]), str(self.hood.pk))

    @patch("apps.notifications.services.NotificationDispatchService.dispatch_sos_alert")
    def test_no_neighborhood_when_outside_every_zone(self, _dispatch):
        resp = auth_client(self.resident).post(
            "/api/sos/",
            {"current_latitude": "-10.000000", "current_longitude": "20.000000"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(resp.data["neighborhood"])

    @patch("apps.notifications.services.NotificationDispatchService.dispatch_sos_alert")
    def test_coordinator_sees_new_alert_in_active_list(self, _dispatch):
        self.NeighborhoodMembership.objects.create(user=self.resident, neighborhood=self.hood, is_primary=True)
        created = auth_client(self.resident).post("/api/sos/", SOS_PAYLOAD, format="json")
        resp = auth_client(self.coordinator).get("/api/sos/active/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(str(created.data["id"]), [str(a["id"]) for a in resp.data])

    @patch("apps.notifications.services.NotificationDispatchService.dispatch_sos_alert")
    def test_client_cannot_choose_neighborhood(self, _dispatch):
        payload = {**SOS_PAYLOAD, "neighborhood": str(self.other_hood.pk)}
        resp = auth_client(self.resident).post("/api/sos/", payload, format="json")
        self.assertNotEqual(str(resp.data["neighborhood"]), str(self.other_hood.pk))
