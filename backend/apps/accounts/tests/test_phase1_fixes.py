"""
Tests for Phase 1 critical fixes.

Covers:
  - CORS origins present in local settings (1.4)
  - JWT env vars read under their documented names (1.5)
  - Logout blacklists the refresh token server-side (1.3 — backend behaviour)
  - Unauthenticated requests to the API return 401, not a redirect (1.2 backend
    counterpart — the backend already behaves correctly; this test codifies it)
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase, RequestFactory, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.models import Role, User


PASSWORD = "ZimSecurePass123!"


def create_role(code):
    return Role.objects.get_or_create(
        code=code,
        defaults={"name": Role.Code(code).label, "is_system": True},
    )[0]


def create_user(*, email="resident@example.com", phone_number="+263771234567", national_id="63-123456A47"):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name="Resident One",
        phone_number=phone_number,
        national_id=national_id,
        role=create_role(Role.Code.RESIDENT),
    )


# ---------------------------------------------------------------------------
# 1.3  Logout blacklists the refresh token
# ---------------------------------------------------------------------------

class LogoutBlacklistsRefreshTokenTests(TestCase):
    """
    Verify the server-side logout blacklists the supplied refresh token so
    that it cannot be used to obtain a new access token after sign-out.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()

    def _login(self):
        response = self.client.post(
            "/api/auth/login",
            {"email": self.user.email, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()["tokens"]

    def test_logout_blacklists_refresh_token(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(
            "/api/auth/logout",
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BlacklistedToken.objects.count(), 1)

    def test_blacklisted_refresh_token_cannot_obtain_new_access_token(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.client.post(
            "/api/auth/logout",
            {"refresh": tokens["refresh"]},
            format="json",
        )

        # Attempt to refresh with the now-blacklisted token.
        refresh_response = self.client.post(
            "/api/auth/refresh",
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_already_blacklisted_token_returns_400(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.client.post("/api/auth/logout", {"refresh": tokens["refresh"]}, format="json")

        # Second logout attempt with the same (now blacklisted) token.
        response = self.client.post(
            "/api/auth/logout",
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_without_refresh_token_returns_400(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post("/api/auth/logout", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_authentication(self):
        response = self.client.post(
            "/api/auth/logout",
            {"refresh": "any-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 1.4  CORS origins in local settings
# ---------------------------------------------------------------------------

class CORSLocalSettingsTests(TestCase):
    """
    Verify that the local development settings expose the Vite dev server
    origins so that browser-side API calls succeed without a proxy.
    """

    def test_vite_origin_present_in_local_cors_settings(self):
        from config.settings import local as local_settings

        cors_origins = getattr(local_settings, "CORS_ALLOWED_ORIGINS", [])
        self.assertIn(
            "http://localhost:5173",
            cors_origins,
            "http://localhost:5173 must be in local CORS_ALLOWED_ORIGINS so the "
            "Vite dev server can reach the API.",
        )
        self.assertIn(
            "http://127.0.0.1:5173",
            cors_origins,
            "http://127.0.0.1:5173 must be in local CORS_ALLOWED_ORIGINS.",
        )

    @override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"])
    def test_cors_preflight_accepted_for_vite_origin(self):
        # Override settings so this test is self-contained regardless of which
        # settings module is active; the production check is in
        # test_vite_origin_present_in_local_cors_settings above.
        response = self.client.options(
            "/api/health/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Access-Control-Allow-Origin", response)


# ---------------------------------------------------------------------------
# 1.5  JWT env var names
# ---------------------------------------------------------------------------

class JWTEnvVarTests(TestCase):
    """
    Verify that the JWT token lifetimes are controlled by the env vars
    documented in .env.example (JWT_ACCESS_TOKEN_EXPIRE_MINUTES and
    JWT_REFRESH_TOKEN_EXPIRE_DAYS) and that the defaults match what README
    documents (60 minutes access, 7 days refresh).
    """

    def test_default_access_token_lifetime_is_60_minutes(self):
        from django.conf import settings

        lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        self.assertEqual(
            lifetime,
            timedelta(minutes=60),
            f"Default access token lifetime should be 60 minutes, got {lifetime}. "
            "Check JWT_ACCESS_TOKEN_EXPIRE_MINUTES in base.py.",
        )

    def test_default_refresh_token_lifetime_is_7_days(self):
        from django.conf import settings

        lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        self.assertEqual(
            lifetime,
            timedelta(days=7),
            f"Default refresh token lifetime should be 7 days, got {lifetime}. "
            "Check JWT_REFRESH_TOKEN_EXPIRE_DAYS in base.py.",
        )

    def test_access_token_lifetime_respects_env_var(self):
        with mock.patch.dict("os.environ", {"JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "30"}):
            # Re-import the env_int helper and re-evaluate the lifetime
            # by importing the module fresh via importlib.
            import importlib
            import config.settings.base as base_mod

            importlib.reload(base_mod)
            lifetime = base_mod.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
            self.assertEqual(lifetime, timedelta(minutes=30))
            # Reload back to default so other tests are not affected.
            importlib.reload(base_mod)

    def test_refresh_token_lifetime_respects_env_var(self):
        with mock.patch.dict("os.environ", {"JWT_REFRESH_TOKEN_EXPIRE_DAYS": "14"}):
            import importlib
            import config.settings.base as base_mod

            importlib.reload(base_mod)
            lifetime = base_mod.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
            self.assertEqual(lifetime, timedelta(days=14))
            importlib.reload(base_mod)


# ---------------------------------------------------------------------------
# 1.2  Unauthenticated API access returns 401 (backend counterpart)
# ---------------------------------------------------------------------------

class ProtectedEndpointsReturn401Tests(TestCase):
    """
    Confirm that protected API endpoints return 401 for unauthenticated
    requests rather than silently redirecting. This is the server-side
    counterpart to the frontend ProtectedRoute fix (1.2).
    """

    def setUp(self):
        self.client = APIClient()

    def test_users_me_requires_authentication(self):
        response = self.client.get("/api/users/me")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_incidents_list_requires_authentication(self):
        response = self.client.get("/api/incidents/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verification_requests_requires_authentication(self):
        response = self.client.post("/api/verification-requests", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_coordinator_queue_requires_authentication(self):
        response = self.client.get("/api/coordinator/verification-requests")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
