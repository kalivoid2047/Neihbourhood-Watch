from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User, VerificationRequest
from apps.audit.models import AuditLog


PASSWORD = "ZimSecurePass123!"


def create_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def create_user(
    *,
    email,
    phone_number,
    national_id,
    role_code=Role.Code.RESIDENT,
):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name=email.split("@")[0].title(),
        phone_number=phone_number,
        national_id=national_id,
        role=create_role(role_code),
    )


class VerificationWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.resident = create_user(
            email="resident@example.com",
            phone_number="+263773333331",
            national_id="63-333331A33",
        )
        self.coordinator = create_user(
            email="coordinator@example.com",
            phone_number="+263773333332",
            national_id="63-333332A33",
            role_code=Role.Code.COORDINATOR,
        )

    def authenticate(self, user):
        response = self.client.post(
            "/api/auth/login",
            {"email": user.email, "password": PASSWORD},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['tokens']['access']}")

    def test_resident_can_create_verification_request(self):
        self.authenticate(self.resident)

        response = self.client.post(
            "/api/verification-requests",
            {"notes": "Please verify my address."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.resident.refresh_from_db()
        verification_request = VerificationRequest.objects.get(user=self.resident)
        self.assertEqual(verification_request.status, VerificationRequest.Status.PENDING)
        self.assertEqual(self.resident.verification_status, User.VerificationStatus.PENDING)
        self.assertTrue(AuditLog.objects.filter(actor=self.resident, action="verification_request").exists())

    def test_duplicate_pending_verification_request_is_rejected(self):
        VerificationRequest.objects.create(user=self.resident)
        self.authenticate(self.resident)

        response = self.client.post("/api/verification-requests", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resident_cannot_list_coordinator_verification_requests(self):
        self.authenticate(self.resident)

        response = self.client.get("/api/coordinator/verification-requests")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_coordinator_can_list_pending_verification_requests(self):
        VerificationRequest.objects.create(user=self.resident)
        self.authenticate(self.coordinator)

        response = self.client.get("/api/coordinator/verification-requests")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)

    def test_coordinator_can_approve_verification_request(self):
        verification_request = VerificationRequest.objects.create(user=self.resident)
        self.authenticate(self.coordinator)

        response = self.client.post(
            f"/api/coordinator/verification-requests/{verification_request.id}/approve",
            {"decision_reason": "Address confirmed."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        verification_request.refresh_from_db()
        self.resident.refresh_from_db()
        self.assertEqual(verification_request.status, VerificationRequest.Status.APPROVED)
        self.assertEqual(verification_request.reviewed_by, self.coordinator)
        self.assertEqual(self.resident.verification_status, User.VerificationStatus.APPROVED)
        self.assertTrue(AuditLog.objects.filter(actor=self.coordinator, action="verification_approval").exists())

    def test_coordinator_can_reject_verification_request(self):
        other_resident = create_user(
            email="other@example.com",
            phone_number="+263773333333",
            national_id="63-333333A33",
        )
        verification_request = VerificationRequest.objects.create(user=other_resident)
        self.authenticate(self.coordinator)

        response = self.client.post(
            f"/api/coordinator/verification-requests/{verification_request.id}/reject",
            {"decision_reason": "Address not confirmed."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        verification_request.refresh_from_db()
        other_resident.refresh_from_db()
        self.assertEqual(verification_request.status, VerificationRequest.Status.REJECTED)
        self.assertEqual(other_resident.verification_status, User.VerificationStatus.REJECTED)
        self.assertTrue(AuditLog.objects.filter(actor=self.coordinator, action="verification_rejection").exists())

