import uuid
from datetime import datetime, timedelta
from io import BytesIO
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership
from apps.incidents.models import Incident, IncidentMedia


class IncidentCRUDTests(TestCase):
    """Tests for incident creation, retrieval, update, and deletion."""

    def setUp(self):
        self.client = APIClient()

        # Create roles
        self.resident_role = Role.objects.create(
            code=Role.Code.RESIDENT,
            name="Resident",
            is_system=True,
        )
        self.coordinator_role = Role.objects.create(
            code=Role.Code.COORDINATOR,
            name="Coordinator",
            is_system=True,
        )
        self.admin_role = Role.objects.create(
            code=Role.Code.SYSTEM_ADMIN,
            name="System Administrator",
            is_system=True,
        )

        # Create neighborhood
        self.neighborhood = Neighborhood.objects.create(
            name="Downtown",
            code="downtown",
            city="Harare",
            province="Harare",
            centroid_latitude="17.8252",
            centroid_longitude="31.0335",
        )

        # Create users
        self.resident1 = User.objects.create_user(
            email="resident1@example.com",
            password="testpass123",
            full_name="Resident One",
            phone_number="+263771111111",
            national_id="12345678A",
            role=self.resident_role,
        )
        self.resident2 = User.objects.create_user(
            email="resident2@example.com",
            password="testpass123",
            full_name="Resident Two",
            phone_number="+263771111112",
            national_id="12345678B",
            role=self.resident_role,
        )
        self.coordinator = User.objects.create_user(
            email="coordinator@example.com",
            password="testpass123",
            full_name="Coordinator",
            phone_number="+263771111113",
            national_id="12345678C",
            role=self.coordinator_role,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            full_name="Admin",
            phone_number="+263771111114",
            national_id="12345678D",
            role=self.admin_role,
        )

        # Create memberships
        NeighborhoodMembership.objects.create(
            user=self.resident1,
            neighborhood=self.neighborhood,
            role=NeighborhoodMembership.Role.RESIDENT,
            is_primary=True,
        )
        NeighborhoodMembership.objects.create(
            user=self.coordinator,
            neighborhood=self.neighborhood,
            role=NeighborhoodMembership.Role.COORDINATOR,
        )

    def test_resident_can_create_incident(self):
        """Residents can create incidents."""
        self.client.force_authenticate(self.resident1)
        data = {
            "neighborhood": str(self.neighborhood.id),
            "title": "Suspicious Activity",
            "description": "Saw someone climbing over fence",
            "category": "suspicious_activity",
            "severity": "blue",
            "latitude": "17.8252",
            "longitude": "31.0335",
            "address": "Main St",
            "occurred_at": (timezone.now() - timedelta(hours=1)).isoformat(),
        }
        response = self.client.post("/api/incidents/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check that response has content
        self.assertIn("title", response.data)

    def test_incident_defaults_to_pending_status(self):
        """Incidents default to PENDING status."""
        incident = Incident.objects.create(
            reporter=self.resident1,
            neighborhood=self.neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        self.assertEqual(incident.status, Incident.Status.PENDING)

    def test_resident_can_update_own_incident(self):
        """Residents can update their own incident before verification."""
        incident = Incident.objects.create(
            reporter=self.resident1,
            neighborhood=self.neighborhood,
            title="Original Title",
            description="Original Description",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        self.client.force_authenticate(self.resident1)
        data = {"title": "Updated Title"}
        response = self.client.patch(f"/api/incidents/{incident.id}/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        incident.refresh_from_db()
        self.assertEqual(incident.title, "Updated Title")

    def test_other_resident_cannot_update_incident(self):
        """Other residents cannot update an incident they didn't report."""
        incident = Incident.objects.create(
            reporter=self.resident1,
            neighborhood=self.neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        self.client.force_authenticate(self.resident2)
        data = {"title": "Updated Title"}
        response = self.client.patch(f"/api/incidents/{incident.id}/", data, format="json")
        # resident2 not in neighborhood, so gets 404 (not found) not 403 (forbidden)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_resident_cannot_view_incident_outside_neighborhood(self):
        """Residents cannot view incidents outside their neighborhood."""
        other_neighborhood = Neighborhood.objects.create(
            name="Suburbs",
            code="suburbs",
            city="Harare",
            province="Harare",
        )
        incident = Incident.objects.create(
            reporter=self.resident1,
            neighborhood=other_neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        self.client.force_authenticate(self.resident2)
        response = self.client.get(f"/api/incidents/{incident.id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_view_all_incidents(self):
        """System admins can view all incidents."""
        incident = Incident.objects.create(
            reporter=self.resident1,
            neighborhood=self.neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/incidents/{incident.id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_incidents_respects_role_and_neighborhood(self):
        """Incident list respects user role and neighborhood membership."""
        incident1 = Incident.objects.create(
            reporter=self.resident1,
            neighborhood=self.neighborhood,
            title="Test 1",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        other_neighborhood = Neighborhood.objects.create(
            name="Suburbs",
            code="suburbs",
            city="Harare",
            province="Harare",
        )
        incident2 = Incident.objects.create(
            reporter=self.resident2,
            neighborhood=other_neighborhood,
            title="Test 2",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )
        self.client.force_authenticate(self.resident1)
        response = self.client.get("/api/incidents/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [inc["id"] for inc in response.data["results"]]
        self.assertIn(str(incident1.id), ids)
        self.assertNotIn(str(incident2.id), ids)


@mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
class IncidentStatusTransitionTests(TestCase):
    """Tests for incident status transitions and verification workflow."""

    def setUp(self):
        self.client = APIClient()

        self.resident_role = Role.objects.create(
            code=Role.Code.RESIDENT,
            name="Resident",
            is_system=True,
        )
        self.coordinator_role = Role.objects.create(
            code=Role.Code.COORDINATOR,
            name="Coordinator",
            is_system=True,
        )

        self.neighborhood = Neighborhood.objects.create(
            name="Downtown",
            code="downtown",
            city="Harare",
            province="Harare",
        )

        self.resident = User.objects.create_user(
            email="resident@example.com",
            password="testpass123",
            full_name="Resident",
            phone_number="+263771111111",
            national_id="12345678A",
            role=self.resident_role,
        )
        self.coordinator = User.objects.create_user(
            email="coordinator@example.com",
            password="testpass123",
            full_name="Coordinator",
            phone_number="+263771111112",
            national_id="12345678B",
            role=self.coordinator_role,
        )

        NeighborhoodMembership.objects.create(
            user=self.coordinator,
            neighborhood=self.neighborhood,
            role=NeighborhoodMembership.Role.COORDINATOR,
        )

        self.incident = Incident.objects.create(
            reporter=self.resident,
            neighborhood=self.neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )

    def test_coordinator_can_verify_pending_incident(self, mock_delay):
        """Coordinators can verify pending incidents."""
        self.client.force_authenticate(self.coordinator)
        data = {"new_status": Incident.Status.VERIFIED}
        response = self.client.post(f"/api/incidents/{self.incident.id}/verify/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.VERIFIED)
        self.assertEqual(self.incident.verified_by_id, self.coordinator.id)
        self.assertIsNotNone(self.incident.verified_at)

    def test_resident_cannot_verify_incident(self, mock_delay):
        """Residents cannot verify incidents."""
        self.client.force_authenticate(self.resident)
        data = {"new_status": Incident.Status.VERIFIED}
        response = self.client.post(f"/api/incidents/{self.incident.id}/verify/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_transition_directly_from_pending_to_resolved(self, mock_delay):
        """Cannot skip from PENDING directly to RESOLVED."""
        self.client.force_authenticate(self.coordinator)
        data = {"new_status": Incident.Status.RESOLVED}
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/transition_status/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_transition_sequence(self, mock_delay):
        """Test valid status transition sequence."""
        self.client.force_authenticate(self.coordinator)

        # PENDING -> VERIFIED
        data = {"new_status": Incident.Status.VERIFIED}
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/transition_status/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.VERIFIED)

        # VERIFIED -> INVESTIGATING
        data = {"new_status": Incident.Status.INVESTIGATING}
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/transition_status/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.INVESTIGATING)

        # INVESTIGATING -> RESOLVED
        data = {"new_status": Incident.Status.RESOLVED}
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/transition_status/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.RESOLVED)


class IncidentMediaUploadTests(TestCase):
    """Tests for incident media upload and validation."""

    def setUp(self):
        self.client = APIClient()

        self.resident_role = Role.objects.create(
            code=Role.Code.RESIDENT,
            name="Resident",
            is_system=True,
        )

        self.neighborhood = Neighborhood.objects.create(
            name="Downtown",
            code="downtown",
            city="Harare",
            province="Harare",
        )

        self.resident = User.objects.create_user(
            email="resident@example.com",
            password="testpass123",
            full_name="Resident",
            phone_number="+263771111111",
            national_id="12345678A",
            role=self.resident_role,
        )

        self.incident = Incident.objects.create(
            reporter=self.resident,
            neighborhood=self.neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )

    def create_test_image(self):
        """Helper to create a test image."""
        image = Image.new("RGB", (100, 100), color="red")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)
        image_io.name = "test.jpg"
        return image_io

    def test_reporter_can_upload_media(self):
        """Incident reporter can upload media."""
        self.client.force_authenticate(self.resident)
        file_obj = self.create_test_image()
        data = {
            "media_type": "image",
            "file": file_obj,
        }
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/upload_media/",
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["media_type"], "image")
        # UUID is returned as string in the response
        self.assertEqual(str(response.data["uploaded_by"]), str(self.resident.id))
        self.assertTrue(IncidentMedia.objects.filter(incident=self.incident).exists())

    def test_unauthenticated_cannot_upload_media(self):
        """Unauthenticated users cannot upload media."""
        file_obj = self.create_test_image()
        data = {
            "media_type": "image",
            "file": file_obj,
        }
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/upload_media/",
            data,
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_incident_media_list(self):
        """Can retrieve list of media for an incident."""
        media1 = IncidentMedia.objects.create(
            incident=self.incident,
            uploaded_by=self.resident,
            media_type="image",
            file="test1.jpg",
            original_filename="test1.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )
        media2 = IncidentMedia.objects.create(
            incident=self.incident,
            uploaded_by=self.resident,
            media_type="video",
            file="test2.mp4",
            original_filename="test2.mp4",
            mime_type="video/mp4",
            size_bytes=2048,
        )
        self.client.force_authenticate(self.resident)
        response = self.client.get(f"/api/incidents/{self.incident.id}/media/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class IncidentAssignmentTests(TestCase):
    """Tests for incident assignment."""

    def setUp(self):
        self.client = APIClient()

        self.resident_role = Role.objects.create(
            code=Role.Code.RESIDENT,
            name="Resident",
            is_system=True,
        )
        self.coordinator_role = Role.objects.create(
            code=Role.Code.COORDINATOR,
            name="Coordinator",
            is_system=True,
        )
        self.police_role = Role.objects.create(
            code=Role.Code.POLICE_OFFICER,
            name="Police Officer",
            is_system=True,
        )

        self.neighborhood = Neighborhood.objects.create(
            name="Downtown",
            code="downtown",
            city="Harare",
            province="Harare",
        )

        self.resident = User.objects.create_user(
            email="resident@example.com",
            password="testpass123",
            full_name="Resident",
            phone_number="+263771111111",
            national_id="12345678A",
            role=self.resident_role,
        )
        self.coordinator = User.objects.create_user(
            email="coordinator@example.com",
            password="testpass123",
            full_name="Coordinator",
            phone_number="+263771111112",
            national_id="12345678B",
            role=self.coordinator_role,
        )
        self.police = User.objects.create_user(
            email="police@example.com",
            password="testpass123",
            full_name="Police Officer",
            phone_number="+263771111113",
            national_id="12345678C",
            role=self.police_role,
        )

        NeighborhoodMembership.objects.create(
            user=self.coordinator,
            neighborhood=self.neighborhood,
        )
        NeighborhoodMembership.objects.create(
            user=self.police,
            neighborhood=self.neighborhood,
        )

        self.incident = Incident.objects.create(
            reporter=self.resident,
            neighborhood=self.neighborhood,
            title="Test",
            description="Test",
            category="theft",
            latitude=17.8252,
            longitude=31.0335,
            occurred_at=timezone.now(),
        )

    def test_coordinator_can_assign_incident(self):
        """Coordinators can assign incidents."""
        self.client.force_authenticate(self.coordinator)
        data = {"assigned_to_id": str(self.police.id)}
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/assign/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_to_id, self.police.id)

    def test_resident_cannot_assign_incident(self):
        """Residents cannot assign incidents."""
        self.client.force_authenticate(self.resident)
        data = {"assigned_to_id": str(self.police.id)}
        response = self.client.post(
            f"/api/incidents/{self.incident.id}/assign/",
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_user_can_view_incident(self):
        """Assigned user can view incident even outside neighborhood."""
        self.incident.assigned_to = self.police
        self.incident.save()

        # Remove police from neighborhood membership
        NeighborhoodMembership.objects.filter(
            user=self.police,
            neighborhood=self.neighborhood,
        ).delete()

        self.client.force_authenticate(self.police)
        response = self.client.get(f"/api/incidents/{self.incident.id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
