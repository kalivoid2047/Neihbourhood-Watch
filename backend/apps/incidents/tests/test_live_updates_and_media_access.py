"""Live-update broadcasts and media/evidence access control."""

from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.incidents.models import Incident, IncidentMedia
from apps.incidents.permissions import user_can_view_incident
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x86\xd9\x03\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_user(n, role_code):
    role = Role.objects.get_or_create(
        code=role_code, defaults={"name": Role.Code(role_code).label, "is_system": True}
    )[0]
    return User.objects.create_user(
        email=f"live{n}@example.com",
        password="ZimSecurePass123!",
        full_name=f"User {n}",
        phone_number=f"+26377{n:07d}",
        national_id=f"63-{n:07d}A47",
        role=role,
    )


class Base(TestCase):
    def setUp(self):
        self.hood = Neighborhood.objects.create(name="Hood", code="hood", city="Harare", province="Harare")
        self.reporter = make_user(1, Role.Code.RESIDENT)
        self.member = make_user(2, Role.Code.RESIDENT)
        self.outsider = make_user(3, Role.Code.RESIDENT)
        self.coordinator = make_user(4, Role.Code.COORDINATOR)
        NeighborhoodMembership.objects.create(user=self.member, neighborhood=self.hood)
        NeighborhoodMembership.objects.create(
            user=self.coordinator, neighborhood=self.hood, role=NeighborhoodMembership.Role.COORDINATOR
        )
        self.incident = Incident.objects.create(
            reporter=self.reporter,
            neighborhood=self.hood,
            title="T",
            description="d",
            category=Incident.Category.THEFT,
            latitude="-17.8",
            longitude="31.0",
            occurred_at=timezone.now(),
        )

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c


class ViewRuleTests(Base):
    def test_resident_member_can_open_incident_shown_in_their_list(self):
        listed = self.client_for(self.member).get("/api/incidents/")
        self.assertIn(str(self.incident.pk), [str(i["id"]) for i in listed.data["results"]])
        detail = self.client_for(self.member).get(f"/api/incidents/{self.incident.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_outsider_cannot_open_incident(self):
        resp = self.client_for(self.outsider).get(f"/api/incidents/{self.incident.pk}/")
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_helper_matches_rules(self):
        self.assertTrue(user_can_view_incident(self.reporter, self.incident))
        self.assertTrue(user_can_view_incident(self.member, self.incident))
        self.assertFalse(user_can_view_incident(self.outsider, self.incident))


@mock.patch("apps.incidents.views.broadcast_incident_update")
class BroadcastOnChangeTests(Base):
    def test_reporter_edit_broadcasts(self, broadcast):
        resp = self.client_for(self.reporter).patch(
            f"/api/incidents/{self.incident.pk}/", {"title": "New"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        broadcast.assert_called_once()

    def test_assign_broadcasts(self, broadcast):
        resp = self.client_for(self.coordinator).post(
            f"/api/incidents/{self.incident.pk}/assign/",
            {"assigned_to_id": str(self.coordinator.pk)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        broadcast.assert_called_once()

    def test_media_upload_and_delete_broadcast(self, broadcast):
        upload = self.client_for(self.reporter).post(
            f"/api/incidents/{self.incident.pk}/upload_media/",
            {"media_type": "image", "file": SimpleUploadedFile("a.png", PNG, content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)
        self.assertEqual(broadcast.call_count, 1)
        deleted = self.client_for(self.reporter).delete(f"/api/media/{upload.data['id']}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(broadcast.call_count, 2)


class MediaAccessTests(Base):
    def setUp(self):
        super().setUp()
        self.media = IncidentMedia.objects.create(
            incident=self.incident,
            uploaded_by=self.reporter,
            media_type="image",
            file="incident-evidence/2026/09/proof.png",
            original_filename="proof.png",
            mime_type="image/png",
            size_bytes=len(PNG),
        )

    def test_outsider_cannot_read_media_record(self):
        resp = self.client_for(self.outsider).get(f"/api/media/{self.media.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_read_media_record(self):
        resp = self.client_for(self.member).get(f"/api/media/{self.media.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @override_settings(DEBUG=False)
    def test_evidence_file_denied_to_outsider(self):
        resp = self.client_for(self.outsider).get("/api/media/incident-evidence/2026/09/proof.png")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(DEBUG=False)
    def test_evidence_file_unknown_path_is_404(self):
        resp = self.client_for(self.member).get("/api/media/incident-evidence/2026/09/nope.png")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(DEBUG=False)
    def test_evidence_file_allowed_to_viewer(self):
        resp = self.client_for(self.member).get("/api/media/incident-evidence/2026/09/proof.png")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["X-Accel-Redirect"], "/protected-media/incident-evidence/2026/09/proof.png")
