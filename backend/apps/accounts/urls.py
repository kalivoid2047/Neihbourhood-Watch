from django.urls import path

from .views import (
    AuthRefreshView,
    DeviceTokenView,
    CoordinatorVerificationRequestListView,
    EmergencyContactDetailView,
    EmergencyContactViewSet,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MyLocationView,
    RegisterView,
    RequestOTPView,
    ResetPasswordView,
    UserProfileView,
    VerificationApproveView,
    VerificationRejectView,
    VerificationRequestCreateView,
    VerifyOTPView,
)


urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/refresh", AuthRefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/request-otp", RequestOTPView.as_view(), name="auth-request-otp"),
    path("auth/verify-otp", VerifyOTPView.as_view(), name="auth-verify-otp"),
    path("auth/forgot-password", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/reset-password", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("users/me", UserProfileView.as_view(), name="users-me"),
    path(
        "verification-requests",
        VerificationRequestCreateView.as_view(),
        name="verification-request-create",
    ),
    path(
        "coordinator/verification-requests",
        CoordinatorVerificationRequestListView.as_view(),
        name="coordinator-verification-request-list",
    ),
    path(
        "coordinator/verification-requests/<uuid:verification_request_id>/approve",
        VerificationApproveView.as_view(),
        name="coordinator-verification-request-approve",
    ),
    path(
        "coordinator/verification-requests/<uuid:verification_request_id>/reject",
        VerificationRejectView.as_view(),
        name="coordinator-verification-request-reject",
    ),
    path("me/location", MyLocationView.as_view(), name="me-location"),
    path("me/device-tokens", DeviceTokenView.as_view(), name="device-tokens"),
    path("me/emergency-contacts", EmergencyContactViewSet.as_view(), name="emergency-contacts-list"),
    path(
        "me/emergency-contacts/<uuid:pk>",
        EmergencyContactDetailView.as_view(),
        name="emergency-contacts-detail",
    ),
]

