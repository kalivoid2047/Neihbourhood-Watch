"""
Tests for Phase 3 changes in the incidents app.

Covers:
  - SHA-256 checksum computed and stored on media upload (3.6)
  - Identical files produce the same checksum (3.6)
  - sync_version starts at 1 after incident creation (3.7)
  - sync_version increments on status transition (3.7)
  - sync_version increments on assign() (3.7)
  - sync_version increments on API PATCH update (3.7)
"""

import hashlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.incidents.models import Incident, IncidentMedia
from apps.incidents.services import IncidentStatusTransitionService
from apps.neighborhoods.models import Neighborhood


PASSWORD = "ZimSecure123!"


def create_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def create_user(
    *,
    email="user@example.com",
    phone_number="+263771000001",
    national_id="63-100001A01",
    role_code=Role.Code.RESIDENT,
):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name="Test User",
        phone_number=phone_number,
        national_id=national_id,
        role=create_role(role_code),
    )


def create_coordinator(
    *,
    email="coord@example.com",
    phone_number="+263771000002",
    national_id="63-100002A02",
):
    return create_user(
        email=email,
        phone_number=phone_number,
        national_id=national_id,
        role_code=Role.Code.COORDINATOR,
    )


def create_neighborhood():
    return Neighborhood.objects.get_or_create(
        code="test-hood",
        defaults={
            "name": "Test Neighborhood",
            "city": "Harare",
            "province": "Harare",
            "centroid_latitude": "-17.8252",
            "centroid_longitude": "31.0335",
        },
    )[0]


def create_incident(user, neighborhood=None, **kwargs):
    if neighborhood is None:
        neighborhood = create_neighborhood()
    defaults = {
        "title": "Test Incident",
        "description": "Something happened here.",
        "category": Incident.Category.THEFT,
        "severity": Incident.Severity.BLUE,
        "reporter": user,
        "neighborhood": neighborhood,
        "latitude": "-17.8252",
        "longitude": "31.0335",
        "occurred_at": timezone.now(),
        "status": Incident.Status.PENDING,
    }
    defaults.update(kwargs)
    return Incident.objects.create(**defaults)


class MediaChecksumTests(TestCase):
    """SHA-256 checksum is stored correctly when media is uploaded."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
        self.incident = create_incident(self.user)

    def _upload(self, content=b"fake image data", name="photo.jpg"):
        upload = SimpleUploadedFile(name, content, content_type="image/jpeg")
        return self.client.post(
            f"/api/incidents/{self.incident.pk}/upload_media/",
            {"file": upload, "media_type": IncidentMedia.MediaType.IMAGE},
            format="multipart",
        )

    def test_checksum_is_stored_after_upload(self):
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        media = IncidentMedia.objects.get(incident=self.incident)
        self.assertTrue(media.checksum, "checksum should be non-empty")

    def test_checksum_is_64_hex_chars(self):
        self._upload()
        media = IncidentMedia.objects.get(incident=self.incident)
        self.assertEqual(len(media.checksum), 64)
        int(media.checksum, 16)  # raises ValueError if not valid hex

    def test_checksum_matches_sha256_of_content(self):
        content = b"deterministic content for checksum test"
        self._upload(content=content)
        media = IncidentMedia.objects.get(incident=self.incident)
        expected = hashlib.sha256(content).hexdigest()
        self.assertEqual(media.checksum, expected)

    def test_identical_files_produce_same_checksum(self):
        content = b"same bytes"
        user2 = create_user(
            email="user2@example.com",
            phone_number="+263771000003",
            national_id="63-100003A03",
        )
        neighborhood = create_neighborhood()
        incident2 = create_incident(user2, neighborhood=neighborhood)
        client2 = APIClient()
        client2.force_authenticate(user2)

        self._upload(content=content, name="file1.jpg")
        upload2 = SimpleUploadedFile("file2.jpg", content, content_type="image/jpeg")
        client2.post(
            f"/api/incidents/{incident2.pk}/upload_media/",
            {"file": upload2, "media_type": IncidentMedia.MediaType.IMAGE},
            format="multipart",
        )

        checksum1 = IncidentMedia.objects.get(incident=self.incident).checksum
        checksum2 = IncidentMedia.objects.get(incident=incident2).checksum
        self.assertEqual(checksum1, checksum2)

    def test_different_files_produce_different_checksums(self):
        user2 = create_user(
            email="user3@example.com",
            phone_number="+263771000004",
            national_id="63-100004A04",
        )
        neighborhood = create_neighborhood()
        incident2 = create_incident(user2, neighborhood=neighborhood)
        client2 = APIClient()
        client2.force_authenticate(user2)

        self._upload(content=b"content-A")
        upload2 = SimpleUploadedFile("b.jpg", b"content-B", content_type="image/jpeg")
        client2.post(
            f"/api/incidents/{incident2.pk}/upload_media/",
            {"file": upload2, "media_type": IncidentMedia.MediaType.IMAGE},
            format="multipart",
        )

        checksum1 = IncidentMedia.objects.get(incident=self.incident).checksum
        checksum2 = IncidentMedia.objects.get(incident=incident2).checksum
        self.assertNotEqual(checksum1, checksum2)


class SyncVersionTests(TestCase):
    """sync_version tracks every mutation: transition, assign, and patch update."""

    def setUp(self):
        self.client = APIClient()
        self.resident = create_user()
        self.coordinator = create_coordinator()
        self.client.force_authenticate(self.resident)
        self.incident = create_incident(self.resident)

    def test_sync_version_starts_at_one(self):
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.sync_version, 1)

    def test_transition_increments_sync_version(self):
        before = self.incident.sync_version
        result = IncidentStatusTransitionService.transition(
            incident=self.incident,
            new_status=Incident.Status.VERIFIED,
            actor=self.coordinator,
        )
        self.assertTrue(result)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.sync_version, before + 1)

    def test_assign_increments_sync_version(self):
        before = self.incident.sync_version
        IncidentStatusTransitionService.assign(
            incident=self.incident,
            assigned_to=self.coordinator,
            actor=self.coordinator,
        )
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.sync_version, before + 1)

    def test_api_patch_increments_sync_version(self):
        before = self.incident.sync_version
        response = self.client.patch(
            f"/api/incidents/{self.incident.pk}/",
            {"description": "Updated description."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.sync_version, before + 1)

    def test_multiple_transitions_each_increment(self):
        initial = self.incident.sync_version

        IncidentStatusTransitionService.transition(
            incident=self.incident,
            new_status=Incident.Status.VERIFIED,
            actor=self.coordinator,
        )
        self.incident.refresh_from_db()
        v1 = self.incident.sync_version

        IncidentStatusTransitionService.transition(
            incident=self.incident,
            new_status=Incident.Status.INVESTIGATING,
            actor=self.coordinator,
        )
        self.incident.refresh_from_db()
        v2 = self.incident.sync_version

        self.assertEqual(v1, initial + 1)
        self.assertEqual(v2, initial + 2)
