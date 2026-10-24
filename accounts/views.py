from django.conf import settings
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from core.permissions import IsOwner, IsSelfOrReadOnly

from .cookies import clear_auth_cookies, set_auth_cookies
from .models import EmergencyContact, InterestTag, Profile
from .serializers import (
    AccountDeleteSerializer,
    EmergencyContactSerializer,
    InterestTagSerializer,
    LoginSerializer,
    PrivateProfileSerializer,
    PublicProfileSerializer,
    RegisterSerializer,
)
from .services import delete_account

_Detail = inline_serializer("Detail", {"detail": serializers.CharField()})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@extend_schema(tags=["auth"], responses={200: _Detail})
@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """GET once when the React app loads: sets the csrftoken cookie."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


@extend_schema(tags=["auth"], responses={201: PrivateProfileSerializer})
class RegisterView(generics.CreateAPIView):
    """Create an account. Requires pdpa_consent = true."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(PrivateProfileSerializer(user.profile).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["auth"],
    request=LoginSerializer,
    responses={200: PrivateProfileSerializer, 401: _Detail},
)
class LoginView(APIView):
    """Log in. Tokens are set as httpOnly cookies and never returned in the body."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=serializer.validated_data["email"].lower(),
            password=serializer.validated_data["password"],
        )
        # authenticate() returns None for wrong credentials AND for
        # suspended/banned/deleted users — same message either way.
        if user is None:
            return Response({"detail": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        response = Response(PrivateProfileSerializer(user.profile).data)
        return set_auth_cookies(response, request, str(refresh.access_token), str(refresh))


@extend_schema(tags=["auth"], request=None, responses={200: _Detail, 401: _Detail})
class RefreshView(APIView):
    """Issue a new access token from the refresh cookie (the refresh token is rotated)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not raw:
            return Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = TokenRefreshSerializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            response = Response({"detail": "Session expired. Please log in again."},
                                status=status.HTTP_401_UNAUTHORIZED)
            return clear_auth_cookies(response)
        data = serializer.validated_data
        response = Response({"detail": "Token refreshed."})
        return set_auth_cookies(response, request, data["access"], data.get("refresh"))


@extend_schema(tags=["auth"], request=None, responses={200: _Detail})
class LogoutView(APIView):
    """Blacklist the refresh token and clear the cookies."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass  # already invalid — nothing to do
        return clear_auth_cookies(Response({"detail": "Logged out."}))


@extend_schema(
    tags=["auth"],
    request=AccountDeleteSerializer,
    responses={204: None, 400: _Detail},
)
class AccountDeleteView(APIView):
    """DELETE /api/auth/account/ — PDPA account deletion (password required)."""

    def delete(self, request):
        serializer = AccountDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            return Response({"detail": "Password is incorrect."},
                            status=status.HTTP_400_BAD_REQUEST)
        delete_account(request.user)
        return clear_auth_cookies(Response(status=status.HTTP_204_NO_CONTENT))


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
@extend_schema(tags=["users"])
class MeView(generics.RetrieveAPIView):
    """The logged-in user's own full profile."""

    serializer_class = PrivateProfileSerializer

    def get_object(self):
        return self.request.user.profile


@extend_schema(tags=["users"])
class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/users/{id}/  — public profile (no login needed).
    PATCH /api/users/{id}/ — edit own profile only.
    """

    queryset = Profile.objects.select_related("user").prefetch_related("interest_tags")
    lookup_field = "user_id"
    lookup_url_kwarg = "pk"
    permission_classes = [IsSelfOrReadOnly]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        # Deleted / banned accounts have no public profile.
        return super().get_queryset().filter(user__status="active")

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsSelfOrReadOnly()]

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return PublicProfileSerializer
        return PrivateProfileSerializer


@extend_schema(tags=["users"])
class EmergencyContactView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET / PUT / DELETE /api/users/{id}/emergency-contact/
    Owner only. Admins get 403 too. PUT creates or replaces the contact.
    """

    serializer_class = EmergencyContactSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    http_method_names = ["get", "put", "delete", "head", "options"]

    def _check_owner(self):
        if int(self.kwargs["pk"]) != self.request.user.pk:
            raise PermissionDenied("Only the owner can access this emergency contact.")

    def get_object(self):
        self._check_owner()
        contact = get_object_or_404(EmergencyContact, user=self.request.user)
        self.check_object_permissions(self.request, contact)
        return contact

    def update(self, request, *args, **kwargs):
        self._check_owner()
        contact = EmergencyContact.objects.filter(user=request.user).first()
        serializer = self.get_serializer(contact, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data,
                        status=status.HTTP_200_OK if contact else status.HTTP_201_CREATED)


@extend_schema(tags=["users"], responses={200: InterestTagSerializer(many=True)})
class InterestTagListView(generics.ListAPIView):
    """All interest tags (for the registration and profile forms)."""

    queryset = InterestTag.objects.all()
    serializer_class = InterestTagSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

