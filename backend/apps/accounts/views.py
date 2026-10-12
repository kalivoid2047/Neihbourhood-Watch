from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.audit.services import create_audit_log, snapshot_model

from .models import DeviceToken, EmergencyContact, OTPChallenge, Role, User, VerificationRequest
from .permissions import HasAnyRole
from .serializers import (
    DeviceTokenSerializer,
    EmergencyContactSerializer,
    ForgotPasswordSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    RegistrationSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
    VerificationDecisionSerializer,
    VerificationRequestCreateSerializer,
    VerificationRequestSerializer,
)
from .services.otp_service import OTPService
from .throttles import LoginThrottle, OTPThrottle, PasswordResetThrottle, RegistrationThrottle


def token_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def otp_response_payload(delivery, detail):
    payload = {
        "detail": detail,
        "challenge_id": delivery.challenge.id,
        "expires_at": delivery.expires_at,
    }
    if getattr(settings, "OTP_EXPOSE_DEBUG_CODES", settings.DEBUG):
        payload["debug_code"] = delivery.code
    return payload


def destination_for(user, channel):
    if channel == OTPChallenge.Channel.EMAIL:
        return user.email
    return user.phone_number


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationThrottle]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        delivery = OTPService().generate(
            user=user,
            purpose=OTPChallenge.Purpose.REGISTRATION,
            channel=OTPChallenge.Channel.EMAIL,
            destination=user.email,
        )
        create_audit_log(
            action="registration",
            actor=user,
            entity=user,
            request=request,
            after=snapshot_model(user),
        )
        return Response(
            {
                "user": UserProfileSerializer(user, context={"request": request}).data,
                "tokens": token_pair_for_user(user),
                "otp": otp_response_payload(delivery, "Registration OTP created."),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        update_last_login(None, user)
        create_audit_log(action="login", actor=user, entity=user, request=request)
        return Response(
            {
                "user": LoginResponseSerializer(user, context={"request": request}).data,
                "tokens": token_pair_for_user(user),
            }
        )


class AuthRefreshView(TokenRefreshView):
    throttle_classes = [LoginThrottle]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError as exc:
            raise ValidationError({"refresh": "Refresh token is invalid or already blacklisted."}) from exc

        create_audit_log(action="logout", actor=request.user, entity=request.user, request=request)
        return Response({"detail": "Logged out successfully."})


class RequestOTPView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.find_user()
        if user is None:
            return Response(
                {"detail": "If the account exists, an OTP challenge has been created."},
                status=status.HTTP_202_ACCEPTED,
            )

        channel = serializer.validated_data["channel"]
        delivery = OTPService().generate(
            user=user,
            purpose=serializer.validated_data["purpose"],
            channel=channel,
            destination=destination_for(user, channel),
        )
        return Response(
            otp_response_payload(
                delivery,
                "If the account exists, an OTP challenge has been created.",
            ),
            status=status.HTTP_202_ACCEPTED,
        )


class VerifyOTPView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.find_user()
        if user is None:
            raise ValidationError({"identifier": "No active OTP challenge was found."})

        try:
            OTPService().verify(
                user=user,
                purpose=serializer.validated_data["purpose"],
                code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            raise ValidationError({"code": exc.messages}) from exc

        if serializer.validated_data["purpose"] in {
            OTPChallenge.Purpose.REGISTRATION,
            OTPChallenge.Purpose.PHONE_VERIFICATION,
        }:
            user.otp_verified_at = timezone.now()
            user.save(update_fields=["otp_verified_at", "updated_at", "last_modified_at"])

        return Response({"detail": "OTP verified successfully."})


class ForgotPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.find_user()
        if user is None:
            return Response(
                {"detail": "If the account exists, password reset instructions have been created."},
                status=status.HTTP_202_ACCEPTED,
            )

        delivery = OTPService().generate(
            user=user,
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
            channel=OTPChallenge.Channel.EMAIL,
            destination=user.email,
        )
        create_audit_log(
            action="password_reset_requested",
            actor=user,
            entity=user,
            request=request,
        )
        return Response(
            otp_response_payload(
                delivery,
                "If the account exists, password reset instructions have been created.",
            ),
            status=status.HTTP_202_ACCEPTED,
        )


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.find_user()
        if user is None:
            raise ValidationError({"email": "No active password reset challenge was found."})

        try:
            OTPService().verify(
                user=user,
                purpose=OTPChallenge.Purpose.PASSWORD_RESET,
                code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            raise ValidationError({"code": exc.messages}) from exc

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at", "last_modified_at"])
        create_audit_log(action="password_reset", actor=user, entity=user, request=request)
        return Response({"detail": "Password reset successfully."})


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        return Response(UserProfileSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        before = snapshot_model(
            request.user,
            fields=["full_name", "phone_number", "address", "latitude", "longitude", "profile_photo"],
        )
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        create_audit_log(
            action="profile_update",
            actor=user,
            entity=user,
            request=request,
            before=before,
            after=snapshot_model(
                user,
                fields=[
                    "full_name",
                    "phone_number",
                    "address",
                    "latitude",
                    "longitude",
                    "profile_photo",
                ],
            ),
        )
        return Response(UserProfileSerializer(user, context={"request": request}).data)


class VerificationRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VerificationRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if request.user.verification_status == User.VerificationStatus.APPROVED:
            raise ValidationError({"detail": "This resident is already verified."})
        if VerificationRequest.objects.filter(
            user=request.user,
            status=VerificationRequest.Status.PENDING,
        ).exists():
            raise ValidationError({"detail": "A pending verification request already exists."})

        with transaction.atomic():
            verification_request = VerificationRequest.objects.create(
                user=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
            request.user.verification_status = User.VerificationStatus.PENDING
            request.user.save(update_fields=["verification_status", "updated_at", "last_modified_at"])

        create_audit_log(
            action="verification_request",
            actor=request.user,
            entity=verification_request,
            request=request,
            after=snapshot_model(verification_request),
        )
        return Response(
            VerificationRequestSerializer(verification_request, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CoordinatorVerificationRequestListView(generics.ListAPIView):
    serializer_class = VerificationRequestSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_role_codes = (Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN)

    def get_queryset(self):
        return (
            VerificationRequest.objects.select_related("user", "reviewed_by", "user__role", "reviewed_by__role")
            .filter(status=VerificationRequest.Status.PENDING)
            .order_by("created_at")
        )


class CoordinatorVerificationDecisionView(APIView):
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_role_codes = (Role.Code.COORDINATOR, Role.Code.SYSTEM_ADMIN)
    decision = None

    def post(self, request, verification_request_id):
        serializer = VerificationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            verification_request = VerificationRequest.objects.select_related("user").get(
                id=verification_request_id
            )
        except VerificationRequest.DoesNotExist as exc:
            raise ValidationError({"detail": "Verification request was not found."}) from exc

        if verification_request.status != VerificationRequest.Status.PENDING:
            raise ValidationError({"detail": "Only pending verification requests can be reviewed."})

        before = snapshot_model(verification_request)
        decision_reason = serializer.validated_data.get("decision_reason", "")
        with transaction.atomic():
            verification_request.reviewed_by = request.user
            verification_request.reviewed_at = timezone.now()
            verification_request.decision_reason = decision_reason
            verification_request.status = self.decision
            verification_request.save(
                update_fields=[
                    "reviewed_by",
                    "reviewed_at",
                    "decision_reason",
                    "status",
                    "updated_at",
                    "last_modified_at",
                ]
            )

            verification_request.user.verification_status = (
                User.VerificationStatus.APPROVED
                if self.decision == VerificationRequest.Status.APPROVED
                else User.VerificationStatus.REJECTED
            )
            verification_request.user.save(
                update_fields=["verification_status", "updated_at", "last_modified_at"]
            )

        action = (
            "verification_approval"
            if self.decision == VerificationRequest.Status.APPROVED
            else "verification_rejection"
        )
        create_audit_log(
            action=action,
            actor=request.user,
            entity=verification_request,
            request=request,
            before=before,
            after=snapshot_model(verification_request),
        )
        return Response(
            VerificationRequestSerializer(verification_request, context={"request": request}).data
        )


class VerificationApproveView(CoordinatorVerificationDecisionView):
    decision = VerificationRequest.Status.APPROVED


class VerificationRejectView(CoordinatorVerificationDecisionView):
    decision = VerificationRequest.Status.REJECTED


class EmergencyContactViewSet(generics.ListCreateAPIView):
    """
    List and create emergency contacts for the authenticated user.

    GET  /api/me/emergency-contacts/   — list
    POST /api/me/emergency-contacts/   — create
    """

    serializer_class = EmergencyContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EmergencyContact.objects.filter(
            user=self.request.user, deleted_at__isnull=True
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class EmergencyContactDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a single emergency contact.

    GET    /api/me/emergency-contacts/{id}/   — retrieve
    PATCH  /api/me/emergency-contacts/{id}/   — update
    DELETE /api/me/emergency-contacts/{id}/   — soft-delete
    """

    serializer_class = EmergencyContactSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return EmergencyContact.objects.filter(
            user=self.request.user, deleted_at__isnull=True
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at", "last_modified_at"])



class DeviceTokenView(APIView):
    """Register or remove this device's push token.

    POST   /api/me/device-tokens   — register (idempotent)
    DELETE /api/me/device-tokens   — remove, on sign-out

    The mobile app calls POST on every launch and whenever FCM rotates the
    token, so this has to be cheap and idempotent rather than erroring on a
    token it has seen before.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # `token` is globally unique: claim it for this user rather than
        # colliding, so a handed-down handset stops alerting its old owner.
        #
        # Goes through `all_objects` on purpose. The default manager hides
        # soft-deleted rows, so an upsert through it would fail to find a
        # previously-removed token and then collide with it on insert — which
        # is exactly what happens when a user signs out and back in again.
        device_token, created = DeviceToken.all_objects.update_or_create(
            token=data["token"],
            defaults={
                "user": request.user,
                "platform": data.get("platform", DeviceToken.Platform.ANDROID),
                "device_id": data.get("device_id", ""),
                "is_active": True,
                "last_seen_at": timezone.now(),
                "deleted_at": None,
            },
        )

        return Response(
            DeviceTokenSerializer(device_token).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        token = (request.data or {}).get("token", "").strip()
        if not token:
            raise ValidationError({"token": "A push token is required."})

        # Deactivate rather than delete, so the row remains available for
        # debugging delivery failures. Scoped to the requesting user so one
        # account cannot unregister another's device.
        updated = DeviceToken.objects.filter(
            user=request.user,
            token=token,
            deleted_at__isnull=True,
        ).update(is_active=False, deleted_at=timezone.now())

        if not updated:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyLocationView(APIView):
    """Report where this user's device currently is.

    POST /api/me/location   {"latitude": ..., "longitude": ...}

    Feeds "who is close by" for incident visibility and SOS alarms.  Clients
    call it on launch and every minute or so while open.  Deliberately cheap:
    one row update, no audit entry.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            lat = round(float(request.data["latitude"]), 6)
            lon = round(float(request.data["longitude"]), 6)
        except (KeyError, TypeError, ValueError):
            raise ValidationError({"latitude": "latitude and longitude are required numbers."})
        if not (-90 <= lat <= 90):
            raise ValidationError({"latitude": "Must be between -90 and 90."})
        if not (-180 <= lon <= 180):
            raise ValidationError({"longitude": "Must be between -180 and 180."})

        User.objects.filter(pk=request.user.pk).update(
            last_latitude=lat, last_longitude=lon, last_location_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
