"""Query filters for the incident list endpoint.

The mobile app's filter sheet and the web dashboard both send repeated query
parameters (``?severity=red&severity=yellow``), so the multi-value filters here
use ``MultipleChoiceFilter``, which ORs the values together.  A plain
``filterset_fields`` list would accept only one value per parameter and
silently drop the rest.
"""

import django_filters
from django.db.models import Q

from .models import Incident


class IncidentFilterSet(django_filters.FilterSet):
    """Filters accepted by ``GET /api/incidents/``.

    Every filter is optional; omitting one widens the result set rather than
    narrowing it, which is what the clients' "no filters selected" state means.
    """

    category = django_filters.MultipleChoiceFilter(
        choices=Incident.Category.choices,
        help_text="Repeatable. e.g. ?category=theft&category=burglary",
    )
    severity = django_filters.MultipleChoiceFilter(
        choices=Incident.Severity.choices,
        help_text="Repeatable. e.g. ?severity=red&severity=yellow",
    )
    status = django_filters.MultipleChoiceFilter(
        choices=Incident.Status.choices,
        help_text="Repeatable. e.g. ?status=pending&status=verified",
    )

    neighborhood = django_filters.UUIDFilter(field_name="neighborhood_id")

    # Time window, used by the dashboard's date pickers.
    occurred_after = django_filters.IsoDateTimeFilter(
        field_name="occurred_at", lookup_expr="gte"
    )
    occurred_before = django_filters.IsoDateTimeFilter(
        field_name="occurred_at", lookup_expr="lte"
    )

    mine = django_filters.BooleanFilter(
        method="filter_mine",
        help_text="?mine=true limits results to incidents you reported.",
    )
    assigned_to_me = django_filters.BooleanFilter(method="filter_assigned_to_me")

    # Only unverified reports, for a coordinator working through a queue.
    unverified = django_filters.BooleanFilter(method="filter_unverified")

    class Meta:
        model = Incident
        fields = [
            "category",
            "severity",
            "status",
            "neighborhood",
            "occurred_after",
            "occurred_before",
            "mine",
            "assigned_to_me",
            "unverified",
        ]

    def filter_mine(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(reporter=self.request.user)

    def filter_assigned_to_me(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(assigned_to=self.request.user)

    def filter_unverified(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(
            Q(verified_at__isnull=True) if value else Q(verified_at__isnull=False)
        )
