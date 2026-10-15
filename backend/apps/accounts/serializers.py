from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers

from .models import DeviceToken, EmergencyContact, OTPChallenge, Role, User, VerificationRequest

# ── Profile photo upload constraints ──────────────────────────────────────────
_PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_PROFILE_PHOTO_ALLOWED_MIME = ("image/jpeg", "image/png", "image/webp", "image/gif")


def _validate_profile_photo(file_obj):
    """Enforce size limit and image-only MIME type for profile photos.

    Uses python-magic when available; falls back to the browser-supplied
    Content-Type header (less reliable but better than nothing).
    """
    if file_obj.size > _PROFILE_PHOTO_MAX_BYTES:
        raise serializers.ValidationError("Profile photo cannot exceed 5 MB.")
    try:
        import magic
        header = file_obj.read(2048)
        file_obj.seek(0)
        detected = magic.from_buffer(header, mime=True)
        if not any(detected.startswith(p) for p in _PROFILE_PHOTO_ALLOWED_MIME):
            raise serializers.ValidationError(
                f"Profile photo must be a JPEG, PNG, WebP, or GIF image (detected: {detected})."
            )
    except ImportError:
        content_type = getattr(file_obj, "content_type", "") or ""
        if content_type and not any(content_type.startswith(p) for p in _PROFILE_PHOTO_ALLOWED_MIME):
            raise serializers.ValidationError("Profile photo must be a JPEG, PNG, WebP, or GIF image.")
    return file_obj


def get_or_create_system_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "description"]


class UserSummarySerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone_number",
            "verification_status",
            "role",
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone_number",
            "national_id",
            "address",
            "latitude",
            "longitude",
            "profile_photo",
            "role",
            "verification_status",
            "otp_verified_at",
            "date_joined",
            "block_captain_applied_at",
        ]
        read_only_fields = [
            "block_captain_applied_at",
            "id",
            "email",
            "national_id",
            "role",
            "verification_status",
            "otp_verified_at",
            "date_joined",
        ]

    def validate_profile_photo(self, value):
        return _validate_profile_photo(value)


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=180)
    phone_number = serializers.CharField(max_length=20)
    national_id = serializers.CharField(max_length=80)
    address = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        min_value=-90,
        max_value=90,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        min_value=-180,
        max_value=180,
    )
    profile_photo = serializers.FileField(required=False, allow_empty_file=False)

    def validate_profile_photo(self, value):
        return _validate_profile_photo(value)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value

    def validate_national_id(self, value):
        if User.objects.filter(national_id=value).exists():
            raise serializers.ValidationError("A user with this national ID already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        role = get_or_create_system_role(Role.Code.RESIDENT)
        password = validated_data.pop("password")
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    password=password,
                    role=role,
                    verification_status=User.VerificationStatus.RESIDENT,
                    **validated_data,
                )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"detail": "A user with these identity details already exists."}
            ) from exc
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class OTPRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    purpose = serializers.ChoiceField(
        choices=OTPChallenge.Purpose.choices,
        default=OTPChallenge.Purpose.PHONE_VERIFICATION,
    )
    channel = serializers.ChoiceField(
        choices=OTPChallenge.Channel.choices,
        default=OTPChallenge.Channel.SMS,
    )

    def find_user(self):
        identifier = self.validated_data["identifier"]
        return User.objects.filter(
            Q(email__iexact=identifier) | Q(phone_number=identifier)
        ).first()


class OTPVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    purpose = serializers.ChoiceField(choices=OTPChallenge.Purpose.choices)
    code = serializers.CharField(min_length=4, max_length=12, trim_whitespace=True)

    def find_user(self):
        identifier = self.validated_data["identifier"]
        return User.objects.filter(
            Q(email__iexact=identifier) | Q(phone_number=identifier)
        ).first()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def find_user(self):
        return User.objects.filter(email__iexact=self.validated_data["email"]).first()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=12, trim_whitespace=True)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def find_user(self):
        return User.objects.filter(email__iexact=self.validated_data["email"]).first()


class VerificationRequestSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    reviewed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = VerificationRequest
        fields = [
            "id",
            "user",
            "status",
            "notes",
            "reviewed_by",
            "reviewed_at",
            "decision_reason",
            "created_at",
            "updated_at",
        ]


class VerificationRequestCreateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class VerificationDecisionSerializer(serializers.Serializer):
    decision_reason = serializers.CharField(required=False, allow_blank=True)


class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = ["id", "name", "phone_number", "relationship", "priority", "can_receive_sos", "created_at"]
        read_only_fields = ["id", "created_at"]


class LoginResponseSerializer(UserProfileSerializer):
    """Subset of the user profile returned in the login response body."""

    class Meta(UserProfileSerializer.Meta):
        fields = [
            "id",
            "email",
            "full_name",
            "phone_number",
            "verification_status",
            "role",
        ]


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Registers a push token for the authenticated user's device.

    Tokens are unique across the whole table, so re-registering a token that
    already belongs to another user must *move* it rather than fail — that is
    exactly what happens when two people share a handset, and the previous
    owner must stop receiving the new owner's alerts.
    """

    # The model's uniqueness constraint would otherwise make ModelSerializer
    # reject any re-registration with a 400.  The app re-registers on every
    # launch, so uniqueness is resolved by the view's upsert instead.
    token = serializers.CharField(validators=[])

    class Meta:
        model = DeviceToken
        fields = ["id", "token", "platform", "device_id", "is_active", "last_seen_at"]
        read_only_fields = ["id", "is_active", "last_seen_at"]

    def validate_token(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("A push token is required.")
        return value
