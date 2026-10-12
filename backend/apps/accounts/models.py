from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import UUIDTimeStampedModel

from .managers import UserManager


phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{9,15}$",
    message="Use an international phone number format with 9 to 15 digits.",
)


class Permission(UUIDTimeStampedModel):
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.code


class Role(UUIDTimeStampedModel):
    class Code(models.TextChoices):
        RESIDENT = "resident", "Resident"
        BLOCK_CAPTAIN = "block_captain", "Block Captain"
        COORDINATOR = "coordinator", "Coordinator"
        POLICE_OFFICER = "police_officer", "Police Officer"
        SYSTEM_ADMIN = "system_admin", "System Administrator"

    code = models.CharField(max_length=40, choices=Code.choices, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    permissions = models.ManyToManyField(
        Permission,
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.name


class RolePermission(UUIDTimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="unique_role_permission",
            )
        ]

    def __str__(self):
        return f"{self.role.code}:{self.permission.code}"


class User(AbstractBaseUser, PermissionsMixin, UUIDTimeStampedModel):
    class VerificationStatus(models.TextChoices):
        RESIDENT = "resident", "Resident"
        PENDING = "pending", "Pending Verification"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=180)
    phone_number = models.CharField(max_length=20, unique=True, validators=[phone_validator])
    national_id = models.CharField(max_length=80, unique=True)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    # Where the user's device last reported itself to be.  Distinct from the
    # home coordinates above: "who is close to this incident right now" is a
    # question about where people are, not where they live.
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    last_location_at = models.DateTimeField(null=True, blank=True)
    profile_photo = models.FileField(upload_to="profiles/", blank=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    verification_status = models.CharField(
        max_length=24,
        choices=VerificationStatus.choices,
        default=VerificationStatus.RESIDENT,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    otp_verified_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "phone_number", "national_id"]

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["national_id"]),
            models.Index(fields=["verification_status"]),
            models.Index(fields=["role", "verification_status"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return self.email

    def effective_location(self, max_age=timedelta(hours=6)):
        """Best guess at where this user is now, as ``(lat, lon)`` floats or ``None``.

        A recent device fix wins; a stale one is ignored (the user has probably
        moved on) and we fall back to the registered home coordinates.
        """
        if (
            self.last_latitude is not None
            and self.last_longitude is not None
            and self.last_location_at
            and timezone.now() - self.last_location_at <= max_age
        ):
            return float(self.last_latitude), float(self.last_longitude)
        if self.latitude is not None and self.longitude is not None:
            return float(self.latitude), float(self.longitude)
        return None


class VerificationRequest(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="verification_requests",
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="verification_reviews",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="pending", deleted_at__isnull=True),
                name="unique_pending_verification_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user.email}:{self.status}"


class DeviceToken(UUIDTimeStampedModel):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_tokens")
    platform = models.CharField(max_length=16, choices=Platform.choices)
    token = models.TextField(unique=True)
    device_id = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "platform", "is_active"]),
            models.Index(fields=["last_seen_at"]),
        ]

    def __str__(self):
        return f"{self.user.email}:{self.platform}"


class EmergencyContact(UUIDTimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=20, validators=[phone_validator])
    relationship = models.CharField(max_length=80, blank=True)
    priority = models.PositiveSmallIntegerField(default=1)
    can_receive_sos = models.BooleanField(default=True)

    class Meta:
        ordering = ("priority", "name")
        indexes = [models.Index(fields=["user", "priority"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "priority"],
                condition=Q(deleted_at__isnull=True),
                name="unique_emergency_contact_priority_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user.email}:{self.name}"


class OTPChallenge(UUIDTimeStampedModel):
    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        LOGIN = "login", "Login"
        PASSWORD_RESET = "password_reset", "Password Reset"
        PHONE_VERIFICATION = "phone_verification", "Phone Verification"

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_challenges")
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    channel = models.CharField(max_length=12, choices=Channel.choices)
    destination = models.CharField(max_length=255)
    hashed_code = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose", "consumed_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.user.email}:{self.purpose}:{self.channel}"

