"""Tests for incident list filtering.

These exist because the failure mode is invisible: before ``filterset_class``
was wired up, the API accepted every filter parameter and returned unfiltered
results.  Nothing errored, so the clients looked broken while the server looked
healthy.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.incidents.models import Incident
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership


_UID = 0


def make_user(role_code=Role.Code.RESIDENT, **kwargs):
    global _UID
    _UID += 1
    role, _ = Role.objects.get_or_create(
        code=role_code,
        defaults={"name": Role.Code(role_code).label, "is_system": True},
    )
    defaults = {
        "email": f"filter{_UID}@test.invalid",
        "full_name": f"Filter User {_UID}",
        "phone_number": f"+2637722{_UID:05d}",
        "national_id": f"72{_UID:07d}C00",
        "password": "ZimSecurePass123!",
        "role": role,
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class IncidentFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.neighborhood = Neighborhood.objects.create(
            name="Filter Hood",
            code="filter-hood",
            city="Cape Town",
            province="Western Cape",
            is_active=True,
        )
        cls.user = make_user()
        NeighborhoodMembership.objects.create(
            neighborhood=cls.neighborhood, user=cls.user
        )
        cls.other = make_user()

        def incident(reporter, **kwargs):
            defaults = {
                "reporter": reporter,
                "neighborhood": cls.neighborhood,
                "title": "Incident",
                "description": "desc",
                "category": Incident.Category.THEFT,
                "severity": Incident.Severity.GREEN,
                "status": Incident.Status.PENDING,
                "latitude": "-33.924900",
                "longitude": "18.424100",
                "occurred_at": timezone.now(),
            }
            defaults.update(kwargs)
            return Incident.objects.create(**defaults)

        cls.critical_theft = incident(
            cls.other,
            title="Critical theft",
            category=Incident.Category.THEFT,
            severity=Incident.Severity.RED,
            status=Incident.Status.VERIFIED,
            verified_at=timezone.now(),
        )
        cls.important_burglary = incident(
            cls.other,
            title="Important burglary",
            category=Incident.Category.BURGLARY,
            severity=Incident.Severity.YELLOW,
        )
        cls.minor_vandalism = incident(
            cls.other,
            title="Minor vandalism",
            category=Incident.Category.VANDALISM,
            severity=Incident.Severity.GREEN,
            status=Incident.Status.RESOLVED,
        )
        cls.my_report = incident(cls.user, title="My own report")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("incidents-list")

    def titles(self, response):
        results = response.json()
        rows = results["results"] if isinstance(results, dict) else results
        return {row["title"] for row in rows}

    def test_returns_everything_without_filters(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Critical theft", self.titles(response))
        self.assertIn("Minor vandalism", self.titles(response))

    def test_filters_by_single_severity(self):
        response = self.client.get(self.url, {"severity": "red"})
        self.assertEqual(self.titles(response), {"Critical theft"})

    def test_filters_by_several_severities(self):
        """Repeated parameters must OR together, not overwrite each other."""
        response = self.client.get(self.url, {"severity": ["red", "yellow"]})
        self.assertEqual(
            self.titles(response), {"Critical theft", "Important burglary"}
        )

    def test_filters_by_category(self):
        response = self.client.get(self.url, {"category": ["burglary", "vandalism"]})
        self.assertEqual(
            self.titles(response), {"Important burglary", "Minor vandalism"}
        )

    def test_filters_by_status(self):
        response = self.client.get(self.url, {"status": "resolved"})
        self.assertEqual(self.titles(response), {"Minor vandalism"})

    def test_combines_filters_with_and(self):
        response = self.client.get(
            self.url, {"severity": ["red", "yellow"], "category": "theft"}
        )
        self.assertEqual(self.titles(response), {"Critical theft"})

    def test_mine_limits_to_own_reports(self):
        response = self.client.get(self.url, {"mine": "true"})
        self.assertEqual(self.titles(response), {"My own report"})

    def test_mine_false_does_not_filter(self):
        response = self.client.get(self.url, {"mine": "false"})
        self.assertIn("Critical theft", self.titles(response))

    def test_unverified_filter(self):
        response = self.client.get(self.url, {"unverified": "true"})
        titles = self.titles(response)
        self.assertNotIn("Critical theft", titles)
        self.assertIn("Important burglary", titles)

    def test_search_matches_title(self):
        response = self.client.get(self.url, {"search": "burglary"})
        self.assertEqual(self.titles(response), {"Important burglary"})

    def test_rejects_an_unknown_severity(self):
        """A typo should be an error, not silently unfiltered results."""
        response = self.client.get(self.url, {"severity": "puce"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ordering_by_occurred_at(self):
        response = self.client.get(self.url, {"ordering": "occurred_at"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
