"""
JWT stored in an httpOnly cookie, with CSRF enforced.

Because the browser attaches cookies automatically, a cookie-based JWT is
vulnerable to CSRF just like a session cookie. So on unsafe methods
(POST/PUT/PATCH/DELETE) we run Django's CSRF check: the request must carry an
X-CSRFToken header matching the csrftoken cookie (double-submit), plus
SameSite=Strict cookies and a CORS allowlist as extra layers.
"""
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason  # return the reason instead of an HttpResponse


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            # Authorization: Bearer ... (Swagger / API clients). Not sent
            # automatically by browsers, so no CSRF risk.
            raw_token = self.get_raw_token(header)
            from_cookie = False
        else:
            raw_token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)
            from_cookie = True

        if raw_token is None:
            return None

        validated = self.get_validated_token(raw_token)
        user = self.get_user(validated)

        if from_cookie:
            self.enforce_csrf(request)
        return user, validated

    @staticmethod
    def enforce_csrf(request):
        check = _CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
