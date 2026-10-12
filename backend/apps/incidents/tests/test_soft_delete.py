from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.incidents.models import Incident


class IncidentSoftDeleteTests(TestCase):
    def test_soft_delete_hides_incident_from_default_manager(self):
        role = Role.objects.create(code=Role.Code.RESIDENT, name="Resident")
        reporter = User.objects.create_user(
            email="reporter@example.com",
            password="secure-password",
            full_name="Reporter",
            phone_number="+263771111111",
            national_id="63-111111A11",
            role=role,
        )
        incident = Incident.objects.create(
            reporter=reporter,
            title="Suspicious vehicle",
            description="Unknown vehicle parked outside homes.",
            category=Incident.Category.SUSPICIOUS_ACTIVITY,
            severity=Incident.Severity.YELLOW,
            latitude=-17.829200,
            longitude=31.052200,
            occurred_at=timezone.now(),
        )

        incident.delete()

        self.assertFalse(Incident.objects.filter(id=incident.id).exists())
        self.assertTrue(Incident.all_objects.filter(id=incident.id, deleted_at__isnull=False).exists())

