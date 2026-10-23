"""Tell drf-spectacular how CookieJWTAuthentication works (removes a schema warning)."""
from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.CookieJWTAuthentication"
    name = "cookieJWT"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": settings.JWT_AUTH_COOKIE}
