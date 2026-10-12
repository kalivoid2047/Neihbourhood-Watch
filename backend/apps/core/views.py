"""Foundation API views."""

import os
import time as _time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse, HttpResponse
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

_SERVICE_START = _time.time()


def _cache_is_healthy() -> bool:
    """Ping the default cache backend; returns False on any error."""
    try:
        cache.set("_nhwz_health", "1", timeout=5)
        return cache.get("_nhwz_health") == "1"
    except Exception:  # pragma: no cover
        return False


class ProtectedMediaView(APIView):
    """Authenticated media file serving view.

    Enforces JWT authentication before a media file is served.

    - When USE_S3_STORAGE=True:  files live in MinIO with pre-signed URLs baked
      into the serializer output, so this endpoint returns 404.
    - When DEBUG=True (runserver): Django serves the file directly from MEDIA_ROOT
      (no nginx available).
    - Production (not DEBUG, not S3): returns an X-Accel-Redirect header so nginx
      can serve the file from the internal /protected-media/ location without an
      extra round-trip through Django.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _authorize_incident_evidence(user, path):
        """Evidence files are only served to users who may view their incident.

        Anything else under MEDIA_ROOT keeps the plain "authenticated" rule.
        Unknown or forbidden evidence paths both return 404 so file names
        cannot be probed.
        """
        if not path.startswith("incident-evidence/"):
            return
        from apps.incidents.models import IncidentMedia
        from apps.incidents.permissions import user_can_view_incident

        media = IncidentMedia.objects.select_related("incident").filter(file=path).first()
        if media is None or not user_can_view_incident(user, media.incident):
            raise NotFound()

    def get(self, request, path):
        if getattr(settings, "USE_S3_STORAGE", False):
            raise NotFound("Media files are served directly from object storage.")

        self._authorize_incident_evidence(request.user, path)

        if settings.DEBUG:
            # Resolve path safely under MEDIA_ROOT, guarding against traversal.
            media_root = str(settings.MEDIA_ROOT)
            full_path = os.path.realpath(os.path.join(media_root, path))
            if not full_path.startswith(media_root + os.sep) and full_path != media_root:
                raise PermissionDenied()
            if not os.path.isfile(full_path):
                raise NotFound()
            return FileResponse(open(full_path, "rb"))  # noqa: WPS515

        # Production: tell nginx to serve the file from the internal location.
        response = HttpResponse()
        response["X-Accel-Redirect"] = f"/protected-media/{path}"
        response["Content-Type"] = ""
        return response


class APIRootView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "service": "Neighbourhood Watch Zimbabwe API",
                "version": "0.1.0",
                "phase": "phase-2-auth-user-verification",
                "endpoints": {
                    "health": request.build_absolute_uri("/api/health/"),
                    "schema": request.build_absolute_uri("/api/schema/"),
                    "register": request.build_absolute_uri("/api/auth/register"),
                    "login": request.build_absolute_uri("/api/auth/login"),
                    "refresh": request.build_absolute_uri("/api/auth/refresh"),
                    "logout": request.build_absolute_uri("/api/auth/logout"),
                    "me": request.build_absolute_uri("/api/users/me"),
                    "verification_requests": request.build_absolute_uri(
                        "/api/verification-requests"
                    ),
                },
            }
        )


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        database_status = "ok"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:  # pragma: no cover - exact driver failures vary.
            database_status = "unavailable"

        cache_status = "ok" if _cache_is_healthy() else "unavailable"

        is_ok = database_status == "ok"
        status_code = 200 if is_ok else 503
        return Response(
            {
                "status": "ok" if is_ok else "degraded",
                "service": "nhwz-api",
                "version": getattr(settings, "APP_VERSION", "unknown"),
                "database": database_status,
                "cache": cache_status,
                "debug": settings.DEBUG,
            },
            status=status_code,
        )


class MetricsView(APIView):
    """Prometheus-compatible metrics endpoint.

    Returns a plain-text document in the Prometheus exposition format
    (version 0.0.4).  Suitable for scraping by Prometheus or Grafana Agent
    without any additional middleware.  No authentication is required so that
    the scraper does not need credentials.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        uptime_seconds = int(_time.time() - _SERVICE_START)
        lines = [
            "# HELP nhwz_up Whether the NHWZ API process is up (1 = up).",
            "# TYPE nhwz_up gauge",
            "nhwz_up 1",
            "# HELP nhwz_uptime_seconds Seconds elapsed since the process started.",
            "# TYPE nhwz_uptime_seconds counter",
            f"nhwz_uptime_seconds {uptime_seconds}",
            "# HELP nhwz_info Static build/version labels.",
            "# TYPE nhwz_info gauge",
            f'nhwz_info{{version="{getattr(settings, "APP_VERSION", "unknown")}"}} 1',
        ]
        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )


class OpenAPISchemaView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        base_url = request.build_absolute_uri("/").rstrip("/")
        return Response(
            {
                "openapi": "3.0.3",
                "info": {
                    "title": "Neighbourhood Watch Zimbabwe API",
                    "version": "0.1.0",
                    "description": "Phase 2 authentication, profile, OTP, and verification API schema.",
                },
                "servers": [{"url": base_url}],
                "paths": {
                    "/api/": {
                        "get": {
                            "summary": "API root",
                            "responses": {"200": {"description": "API metadata"}},
                        }
                    },
                    "/api/health/": {
                        "get": {
                            "summary": "Health check",
                            "responses": {
                                "200": {"description": "Service healthy"},
                                "503": {"description": "Service degraded"},
                            },
                        }
                    },
                    "/api/token/": {
                        "post": {
                            "summary": "Obtain JWT access and refresh tokens",
                            "responses": {"200": {"description": "JWT token pair"}},
                        }
                    },
                    "/api/token/refresh/": {
                        "post": {
                            "summary": "Legacy JWT refresh endpoint",
                            "responses": {"200": {"description": "JWT access token"}},
                        }
                    },
                    "/api/auth/register": {
                        "post": {
                            "summary": "Register a resident account",
                            "description": "Creates a resident, issues JWT tokens, creates a registration OTP, and writes a registration audit log.",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "email": "resident@example.com",
                                            "password": "ZimSecurePass123!",
                                            "full_name": "Resident One",
                                            "phone_number": "+263771234567",
                                            "national_id": "63-123456A47",
                                            "address": "Avondale, Harare",
                                            "latitude": "-17.789123",
                                            "longitude": "31.044456",
                                        }
                                    }
                                },
                            },
                            "responses": {"201": {"description": "Resident registered"}},
                        }
                    },
                    "/api/auth/login": {
                        "post": {
                            "summary": "Login with email and password",
                            "description": "Returns a refresh/access token pair and writes a login audit log.",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "email": "resident@example.com",
                                            "password": "ZimSecurePass123!",
                                        }
                                    }
                                },
                            },
                            "responses": {"200": {"description": "Authenticated"}},
                        }
                    },
                    "/api/auth/refresh": {
                        "post": {
                            "summary": "Refresh JWT tokens",
                            "description": "Uses Simple JWT refresh token rotation and blacklisting.",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {"example": {"refresh": "<refresh-token>"}}
                                },
                            },
                            "responses": {"200": {"description": "Token refreshed"}},
                        }
                    },
                    "/api/auth/logout": {
                        "post": {
                            "summary": "Logout and blacklist refresh token",
                            "security": [{"bearerAuth": []}],
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {"example": {"refresh": "<refresh-token>"}}
                                },
                            },
                            "responses": {"200": {"description": "Logged out"}},
                        }
                    },
                    "/api/auth/request-otp": {
                        "post": {
                            "summary": "Request OTP",
                            "description": "Creates a database-backed OTP challenge for phone verification, registration, login, or password reset.",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "identifier": "resident@example.com",
                                            "purpose": "phone_verification",
                                            "channel": "sms",
                                        }
                                    }
                                },
                            },
                            "responses": {"202": {"description": "OTP challenge accepted"}},
                        }
                    },
                    "/api/auth/verify-otp": {
                        "post": {
                            "summary": "Verify OTP",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "identifier": "resident@example.com",
                                            "purpose": "phone_verification",
                                            "code": "123456",
                                        }
                                    }
                                },
                            },
                            "responses": {"200": {"description": "OTP verified"}},
                        }
                    },
                    "/api/auth/forgot-password": {
                        "post": {
                            "summary": "Create password reset OTP",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "example": {"email": "resident@example.com"}
                                    }
                                },
                            },
                            "responses": {"202": {"description": "Password reset accepted"}},
                        }
                    },
                    "/api/auth/reset-password": {
                        "post": {
                            "summary": "Reset password with OTP",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "email": "resident@example.com",
                                            "code": "123456",
                                            "new_password": "NewZimSecurePass123!",
                                        }
                                    }
                                },
                            },
                            "responses": {"200": {"description": "Password reset"}},
                        }
                    },
                    "/api/users/me": {
                        "get": {
                            "summary": "Get current user profile",
                            "security": [{"bearerAuth": []}],
                            "responses": {"200": {"description": "Current user profile"}},
                        },
                        "patch": {
                            "summary": "Update current user profile",
                            "security": [{"bearerAuth": []}],
                            "description": "Supports JSON and multipart profile image updates. Role and verification fields are read-only.",
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "full_name": "Resident Updated",
                                            "address": "Borrowdale, Harare",
                                            "phone_number": "+263771234568",
                                        }
                                    }
                                }
                            },
                            "responses": {"200": {"description": "Profile updated"}},
                        },
                    },
                    "/api/verification-requests": {
                        "post": {
                            "summary": "Create resident verification request",
                            "security": [{"bearerAuth": []}],
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "example": {"notes": "Please verify my residence."}
                                    }
                                }
                            },
                            "responses": {"201": {"description": "Verification request created"}},
                        }
                    },
                    "/api/coordinator/verification-requests": {
                        "get": {
                            "summary": "List pending verification requests",
                            "security": [{"bearerAuth": []}],
                            "description": "Coordinator and system administrator roles only.",
                            "responses": {"200": {"description": "Pending verification requests"}},
                        }
                    },
                    "/api/coordinator/verification-requests/{id}/approve": {
                        "post": {
                            "summary": "Approve verification request",
                            "security": [{"bearerAuth": []}],
                            "parameters": [
                                {"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
                            ],
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "example": {"decision_reason": "Address confirmed."}
                                    }
                                }
                            },
                            "responses": {"200": {"description": "Verification approved"}},
                        }
                    },
                    "/api/coordinator/verification-requests/{id}/reject": {
                        "post": {
                            "summary": "Reject verification request",
                            "security": [{"bearerAuth": []}],
                            "parameters": [
                                {"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
                            ],
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "example": {"decision_reason": "Address could not be confirmed."}
                                    }
                                }
                            },
                            "responses": {"200": {"description": "Verification rejected"}},
                        }
                    },
                },
                "components": {
                    "securitySchemes": {
                        "bearerAuth": {
                            "type": "http",
                            "scheme": "bearer",
                            "bearerFormat": "JWT",
                        }
                    },
                    "schemas": {
                        "AuthTokenPair": {
                            "type": "object",
                            "properties": {
                                "refresh": {"type": "string"},
                                "access": {"type": "string"},
                            },
                        },
                        "APIError": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                },
            }
        )
