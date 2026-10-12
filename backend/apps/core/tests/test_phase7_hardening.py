"""Phase 7: Production hardening tests.

Covers:
- Enhanced health-check (cache status, version field)
- Prometheus-compatible metrics endpoint
- RequestLoggingMiddleware structured logging
- Security header presence
- DRF throttle configuration
"""

from unittest import mock

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient


# ── Health check (enhanced) ────────────────────────────────────────────────────

class HealthCheckEnhancedTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_returns_200(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.status_code, 200)

    def test_health_includes_cache_status(self):
        resp = self.client.get("/api/health/")
        self.assertIn("cache", resp.json())

    def test_health_cache_ok_when_cache_works(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.json()["cache"], "ok")

    def test_health_includes_version_field(self):
        resp = self.client.get("/api/health/")
        self.assertIn("version", resp.json())

    def test_health_version_matches_setting(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.json()["version"], getattr(settings, "APP_VERSION", "unknown"))

    def test_health_cache_unavailable_when_cache_is_unhealthy(self):
        # Mock the isolated helper so DRF throttle's own cache.set is unaffected.
        with mock.patch("apps.core.views._cache_is_healthy", return_value=False):
            resp = self.client.get("/api/health/")
        self.assertEqual(resp.json()["cache"], "unavailable")
        # DB still ok → overall status and HTTP code unaffected.
        self.assertEqual(resp.json()["status"], "ok")
        self.assertEqual(resp.status_code, 200)


# ── Prometheus metrics endpoint ────────────────────────────────────────────────

class MetricsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_metrics_returns_200(self):
        resp = self.client.get("/api/metrics/")
        self.assertEqual(resp.status_code, 200)

    def test_metrics_content_type_is_text_plain(self):
        resp = self.client.get("/api/metrics/")
        self.assertIn("text/plain", resp["Content-Type"])

    def test_metrics_contains_nhwz_up(self):
        resp = self.client.get("/api/metrics/")
        self.assertIn(b"nhwz_up 1", resp.content)

    def test_metrics_contains_uptime(self):
        resp = self.client.get("/api/metrics/")
        self.assertIn(b"nhwz_uptime_seconds", resp.content)

    def test_metrics_contains_info_label(self):
        resp = self.client.get("/api/metrics/")
        self.assertIn(b"nhwz_info", resp.content)

    def test_metrics_requires_no_authentication(self):
        # A fresh client with no credentials must still get 200.
        resp = APIClient().get("/api/metrics/")
        self.assertEqual(resp.status_code, 200)

    def test_metrics_prometheus_help_lines_present(self):
        resp = self.client.get("/api/metrics/")
        self.assertIn(b"# HELP nhwz_up", resp.content)
        self.assertIn(b"# TYPE nhwz_up gauge", resp.content)


# ── RequestLoggingMiddleware ───────────────────────────────────────────────────

class RequestLoggingMiddlewareTests(TestCase):
    @mock.patch("apps.core.middleware.logger")
    def test_logs_every_request(self, mock_logger):
        APIClient().get("/api/health/")
        self.assertTrue(mock_logger.info.called, "Expected logger.info to be called")

    @mock.patch("apps.core.middleware.logger")
    def test_log_contains_method_and_path(self, mock_logger):
        APIClient().get("/api/health/")
        _msg, kwargs = mock_logger.info.call_args
        extra = kwargs["extra"]
        self.assertEqual(extra["method"], "GET")
        self.assertEqual(extra["path"], "/api/health/")

    @mock.patch("apps.core.middleware.logger")
    def test_log_contains_status_code(self, mock_logger):
        APIClient().get("/api/health/")
        extra = mock_logger.info.call_args[1]["extra"]
        self.assertEqual(extra["status_code"], 200)

    @mock.patch("apps.core.middleware.logger")
    def test_log_contains_duration_ms(self, mock_logger):
        APIClient().get("/api/health/")
        extra = mock_logger.info.call_args[1]["extra"]
        self.assertIn("duration_ms", extra)
        self.assertIsInstance(extra["duration_ms"], int)
        self.assertGreaterEqual(extra["duration_ms"], 0)

    @mock.patch("apps.core.middleware.logger")
    def test_log_user_id_none_for_anonymous(self, mock_logger):
        APIClient().get("/api/health/")
        extra = mock_logger.info.call_args[1]["extra"]
        self.assertIsNone(extra["user_id"])


# ── Security headers ───────────────────────────────────────────────────────────

class SecurityHeaderTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_x_frame_options_is_deny(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.get("X-Frame-Options"), "DENY")

    def test_x_content_type_options_nosniff(self):
        # SECURE_CONTENT_TYPE_NOSNIFF=True in base.py → SecurityMiddleware adds header.
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.get("X-Content-Type-Options"), "nosniff")


# ── Throttle configuration ─────────────────────────────────────────────────────

class ThrottleConfigTests(TestCase):
    def test_default_throttle_classes_are_configured(self):
        classes = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_CLASSES", [])
        self.assertIn("rest_framework.throttling.AnonRateThrottle", classes)
        self.assertIn("rest_framework.throttling.UserRateThrottle", classes)

    def test_anon_throttle_rate_is_defined(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        self.assertIn("anon", rates)

    def test_user_throttle_rate_is_defined(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        self.assertIn("user", rates)

    def test_auth_endpoint_throttle_rates_still_present(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        for key in ("auth_register", "auth_login", "auth_otp", "auth_password_reset"):
            self.assertIn(key, rates, f"Missing throttle rate for '{key}'")
