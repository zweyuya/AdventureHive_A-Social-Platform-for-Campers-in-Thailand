"""
AdventureHive settings.

All secrets and environment-specific values come from environment variables
(or a local .env file). Copy .env.example to .env for development.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    SECURE_SSL_REDIRECT=(bool, False),
    JWT_COOKIE_SECURE=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    # AdventureHive
    "core",
    "accounts",
    "locations",
    "communities",
    "trips",
    "reviews",
    "qa",
    "social",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------
# Database (PostgreSQL only — triggers and constraints rely on it)
# --------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# bcrypt first (work factor 12 is the Django default for BCryptSHA256).
# The others remain so existing hashes still verify.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Reads the JWT from an httpOnly cookie and enforces CSRF on unsafe methods.
        "accounts.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "rsvp": "10/min",    # used by the RSVP endpoint (RSVP flooding mitigation)
        "auth": "10/min",    # login / register
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AdventureHive API",
    "DESCRIPTION": "Camping community platform for Thailand.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Give shared choice sets one clear name in the API docs
    "ENUM_NAME_OVERRIDES": {
        "ExperienceLevelEnum": "core.models.ExperienceLevel",
        "TripStatusEnum": "trips.models.TripStatus",
        "ParticipantStatusEnum": "trips.models.ParticipantStatus",
        "AttendanceStatusEnum": [("attended", "Attended"), ("no_show", "No-show")],
        "LocationStatusEnum": "locations.models.LocationStatus",
        "RevisionStatusEnum": "locations.models.RevisionStatus",
        "UserStatusEnum": "accounts.models.UserStatus",
        "ContentStatusEnum": "reviews.models.ReviewStatus",  # published / hidden
        "QuestionStatusEnum": "qa.models.QuestionStatus",
        "GroupMemberStatusEnum": "communities.models.GroupMemberStatus",
        "PostStatusEnum": "social.models.PostStatus",
        "ReactionTypeEnum": "social.models.ReactionType",
        "GroupMemberRoleEnum": "communities.models.GroupMemberRole",
        "GroupCategoryEnum": "communities.models.GroupCategory",
        "CampsiteCategoryEnum": "locations.models.LocationCategory",
    },
}

# --------------------------------------------------------------------------
# JWT in httpOnly cookies
# --------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

JWT_AUTH_COOKIE = "ah_access"
JWT_REFRESH_COOKIE = "ah_refresh"
JWT_COOKIE_SECURE = env("JWT_COOKIE_SECURE")
JWT_COOKIE_SAMESITE = "Strict"
JWT_COOKIE_PATH = "/"
JWT_REFRESH_COOKIE_PATH = "/api/auth/"

# CSRF: double-submit. React reads the (non-httpOnly) csrftoken cookie and
# sends it back in the X-CSRFToken header on POST/PUT/PATCH/DELETE.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = JWT_COOKIE_SECURE
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
if DEBUG:  # the Vite dev server can be opened as localhost or 127.0.0.1
    CSRF_TRUSTED_ORIGINS += [o for o in ("http://localhost:5173", "http://127.0.0.1:5173")
                             if o not in CSRF_TRUSTED_ORIGINS]
SESSION_COOKIE_SECURE = JWT_COOKIE_SECURE

# CORS is only needed in development (React dev server on another port).
# In production, serve React and the API from the same origin.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --------------------------------------------------------------------------
# HTTPS / security headers (enable via env on the server)
# --------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------
# Field-level encryption (emergency contacts)
# Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# --------------------------------------------------------------------------
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")

# --------------------------------------------------------------------------
# I18N / static
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_URL_ABS = "/media/"  # site-relative prefix used in API responses
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024  # campsite photos are capped at 5 MB

# Never log request bodies (they can contain passwords / emergency contacts).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
