"""Helpers for putting JWTs into httpOnly cookies."""
from django.conf import settings
from django.middleware.csrf import get_token

ACCESS_MAX_AGE = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
REFRESH_MAX_AGE = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_auth_cookies(response, request, access: str, refresh: str | None = None):
    common = {
        "httponly": True,  # not readable by JavaScript → XSS cannot steal tokens
        "secure": settings.JWT_COOKIE_SECURE,  # HTTPS only in production
        "samesite": settings.JWT_COOKIE_SAMESITE,
    }
    response.set_cookie(
        settings.JWT_AUTH_COOKIE, access, max_age=ACCESS_MAX_AGE,
        path=settings.JWT_COOKIE_PATH, **common,
    )
    if refresh:
        # Refresh token is only ever sent to /api/auth/* (refresh, logout, account).
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE, refresh, max_age=REFRESH_MAX_AGE,
            path=settings.JWT_REFRESH_COOKIE_PATH, **common,
        )
    # Make sure the browser has a csrftoken cookie for the double-submit check.
    get_token(request)
    return response


def clear_auth_cookies(response):
    response.delete_cookie(
        settings.JWT_AUTH_COOKIE, path=settings.JWT_COOKIE_PATH,
        samesite=settings.JWT_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE, path=settings.JWT_REFRESH_COOKIE_PATH,
        samesite=settings.JWT_COOKIE_SAMESITE,
    )
    return response
