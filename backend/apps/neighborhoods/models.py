from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import UUIDTimeStampedModel


class Neighborhood(UUIDTimeStampedModel):
    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=120)
    province = models.CharField(max_length=120)
    boundary_geojson = models.JSONField(null=True, blank=True)
    centroid_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    centroid_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    alert_radius_m = models.PositiveIntegerField(default=5000)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["province", "city"]),
            models.Index(fields=["centroid_latitude", "centroid_longitude"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class NeighborhoodMembership(UUIDTimeStampedModel):
    class Role(models.TextChoices):
        RESIDENT = "resident", "Resident"
        BLOCK_CAPTAIN = "block_captain", "Block Captain"
        COORDINATOR = "coordinator", "Coordinator"
        POLICE_LIAISON = "police_liaison", "Police Liaison"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="neighborhood_memberships",
    )
    neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.RESIDENT)
    is_primary = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "role"]),
            models.Index(fields=["neighborhood", "role"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "neighborhood"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_neighborhood_membership",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_primary=True, deleted_at__isnull=True),
                name="unique_primary_neighborhood_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user}:{self.neighborhood}"

