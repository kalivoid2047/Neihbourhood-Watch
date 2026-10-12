from rest_framework.throttling import SimpleRateThrottle


class ScopedIPThrottle(SimpleRateThrottle):
    scope = None

    def get_cache_key(self, request, view):
        if self.scope is None:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class RegistrationThrottle(ScopedIPThrottle):
    scope = "auth_register"


class LoginThrottle(ScopedIPThrottle):
    scope = "auth_login"


class OTPThrottle(ScopedIPThrottle):
    scope = "auth_otp"


class PasswordResetThrottle(ScopedIPThrottle):
    scope = "auth_password_reset"

