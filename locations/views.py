from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import filters, mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.permissions import CanModerateCampsites
from core.provinces import check_pin

from . import services
from .filters import CampsiteFilter
from .models import Authority, Location, LocationRevision, LocationStatus, RevisionStatus
from .serializers import (
    AuthoritySerializer,
    CampsiteDetailSerializer,
    CampsiteListSerializer,
    CampsiteWriteSerializer,
    PendingCampsiteSerializer,
    PinCheckSerializer,
    RejectSerializer,
    RevisionSerializer,
    SuggestEditSerializer,
)


class CampsitePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


_FILTER_BACKENDS = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["campsites"])
class CampsiteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin,
                      viewsets.GenericViewSet):
    """
    Public browsing of published campsites, plus the member submission workflow.

    list / retrieve     — anyone; published campsites and ones waiting for a moderator
                          ("Not yet verified"); submitters also see their own drafts
    create              — members; creates a DRAFT (not public)
    update / partial    — the submitter, only while draft or rejected
    submit              — the submitter: draft/rejected → pending_review
    moderation          — moderators: submissions waiting for a decision, oldest first
    approve / reject    — moderators: pending_review → published / rejected (note required)
    mine                — the member's own submissions with their status
    pin-check           — members: province / inside-Thailand / nearby campsites for a map pin
    revisions (POST)    — suggest an edit to a published campsite (pending until approved)
    history             — approved versions of a campsite
    """

    pagination_class = CampsitePagination
    filter_backends = _FILTER_BACKENDS
    filterset_class = CampsiteFilter
    search_fields = ["name", "province", "description"]
    ordering_fields = ["name", "avg_rating", "review_count", "created_at"]
    ordering = ["name"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = Location.objects.select_related("authority")
        user = self.request.user
        if self.action == "list":
            return qs.visible()
        if self.action in ("approve", "reject"):
            return qs  # moderators only, see get_permissions
        if user.is_authenticated and user.is_staff:
            return qs
        if user.is_authenticated:
            return qs.filter(Q(pk__in=Location.objects.visible().values("pk")) | Q(created_by=user))
        return qs.visible()

    def get_permissions(self):
        if self.action in ("list", "retrieve", "history"):
            return [permissions.AllowAny()]
        if self.action in ("moderation", "approve", "reject"):
            return [permissions.IsAuthenticated(), CanModerateCampsites()]
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action == "submit":  # unchecked campsites are public, so limit how many go out
            self.throttle_scope = "campsite_submit"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        return {
            "list": CampsiteListSerializer,
            "mine": CampsiteListSerializer,
            "create": CampsiteWriteSerializer,
            "update": CampsiteWriteSerializer,
            "partial_update": CampsiteWriteSerializer,
            "reject": RejectSerializer,
            "revisions": SuggestEditSerializer,
            "history": RevisionSerializer,
        }.get(self.action, CampsiteDetailSerializer)

    # ---- create / edit own draft -------------------------------------------
    @extend_schema(responses={201: CampsiteDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save(created_by=request.user, status=LocationStatus.DRAFT)
        return Response(CampsiteDetailSerializer(location, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses=CampsiteDetailSerializer)
    def update(self, request, *args, **kwargs):
        location = self.get_object()
        if location.created_by_id != request.user.pk:
            raise PermissionDenied("Only the submitter can edit this submission. "
                                   "Use 'suggest an edit' for published campsites.")
        if location.status not in (LocationStatus.DRAFT, LocationStatus.REJECTED):
            raise ValidationError(f"A {location.status} campsite cannot be edited directly.")
        serializer = self.get_serializer(location, data=request.data,
                                         partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CampsiteDetailSerializer(location, context={"request": request}).data)

    # ---- moderation queue ----------------------------------------------------
    @extend_schema(responses=PendingCampsiteSerializer(many=True))
    @action(detail=False, methods=["get"])
    def moderation(self, request):
        """Campsites waiting for a decision, oldest first, with pin check and possible duplicates."""
        qs = Location.objects.filter(status=LocationStatus.PENDING_REVIEW) \
            .select_related("authority", "created_by__profile").order_by("updated_at", "pk")
        page = self.paginate_queryset(qs)
        data = PendingCampsiteSerializer(page, many=True, context={"request": request}).data
        return self.get_paginated_response(data)

    # ---- workflow actions ----------------------------------------------------
    @extend_schema(request=None, responses=CampsiteDetailSerializer)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        location = services.submit(self.get_object(), request.user)
        return Response(CampsiteDetailSerializer(location, context={"request": request}).data)

    @extend_schema(request=None, responses=CampsiteDetailSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        location = services.approve_submission(self.get_object(), request.user)
        return Response(CampsiteDetailSerializer(location, context={"request": request}).data)

    @extend_schema(request=RejectSerializer, responses=CampsiteDetailSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = services.reject_submission(self.get_object(), request.user,
                                              serializer.validated_data["note"])
        return Response(CampsiteDetailSerializer(location, context={"request": request}).data)

    @extend_schema(responses=CampsiteDetailSerializer(many=True))
    @action(detail=False, methods=["get"])
    def mine(self, request):
        """The logged-in member's own submissions (any status), with moderation notes."""
        qs = Location.objects.filter(created_by=request.user).order_by("-created_at")
        data = CampsiteDetailSerializer(qs, many=True, context={"request": request}).data
        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter("lat", OpenApiTypes.FLOAT, required=True),
            OpenApiParameter("lng", OpenApiTypes.FLOAT, required=True),
            OpenApiParameter("exclude", OpenApiTypes.INT,
                             description="Campsite id to leave out of 'nearby' (the one being edited)"),
        ],
        responses=PinCheckSerializer,
    )
    @action(detail=False, methods=["get"], url_path="pin-check")
    def pin_check(self, request):
        """Where is this map pin? Province, inside Thailand or not, and campsites within 1 km."""
        params = request.query_params
        try:
            lat, lng = float(params["lat"]), float(params["lng"])
            exclude = int(params["exclude"]) if params.get("exclude") else None
        except (KeyError, ValueError):
            raise ValidationError({"detail": "Give numeric lat and lng (and exclude, if used)."})
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValidationError({"detail": "lat/lng out of range."})
        pin = check_pin(lat, lng)
        # Include ones waiting for a moderator, so people don't submit the same place twice.
        nearby = services.nearby_campsites(lat, lng, queryset=Location.objects.visible(),
                                           exclude_id=exclude)
        return Response(PinCheckSerializer({
            "latitude": lat, "longitude": lng, "in_thailand": pin.in_thailand,
            "country": pin.country, "province": pin.province, "provinces": sorted(pin.allowed),
            "nearby": [{"id": loc.id, "name": loc.name, "province": loc.province,
                        "verified": loc.status == LocationStatus.PUBLISHED,
                        "distance_km": round(d, 2)} for loc, d in nearby],
        }).data)

    @extend_schema(request=SuggestEditSerializer, responses={201: RevisionSerializer})
    @action(detail=True, methods=["post"])
    def revisions(self, request, pk=None):
        """Suggest an edit to a published campsite. Applied only after staff approval."""
        location = get_object_or_404(Location.objects.published(), pk=pk)
        serializer = SuggestEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        summary = changes.pop("edit_summary")
        revision = services.propose_edit(location, request.user, changes, summary)
        return Response(RevisionSerializer(revision).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=RevisionSerializer(many=True))
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Approved versions, newest first: who changed what, and when."""
        location = get_object_or_404(Location.objects.visible(), pk=pk)  # none until approved
        qs = location.revisions.filter(status=RevisionStatus.APPROVED) \
            .select_related("edited_by__profile").order_by("-version_no")
        return Response(RevisionSerializer(qs, many=True).data)


@extend_schema(tags=["campsites"])
class RevisionModerationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Staff queue of suggested edits."""

    serializer_class = RevisionSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = None
    queryset = LocationRevision.objects.filter(status=RevisionStatus.PENDING) \
        .select_related("edited_by__profile").order_by("created_at")

    @extend_schema(request=None, responses=RevisionSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        revision = get_object_or_404(LocationRevision, pk=pk)
        return Response(RevisionSerializer(services.approve_revision(revision, request.user)).data)

    @extend_schema(request=RejectSerializer, responses=RevisionSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        revision = get_object_or_404(LocationRevision, pk=pk)
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revision = services.reject_revision(revision, request.user,
                                            serializer.validated_data["note"])
        return Response(RevisionSerializer(revision).data)


@extend_schema(
    tags=["campsites"],
    responses=inline_serializer("CampsiteFeatureCollection", {
        "type": serializers.CharField(),
        "features": serializers.ListField(child=serializers.DictField()),
    }),
)
class CampsiteMapView(APIView):
    """
    Lightweight GeoJSON for the map (published and not-yet-verified campsites, no pagination).
    Accepts the same filters as the list.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = CampsiteFilter(request.GET, queryset=Location.objects.visible()).qs
        rows = qs.values("id", "name", "category", "province", "avg_rating",
                         "latitude", "longitude", "cover_image", "status")
        features = [
            {
                "type": "Feature",
                # GeoJSON order is [longitude, latitude]
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "id": r["id"], "name": r["name"], "category": r["category"],
                    "province": r["province"],
                    "verified": r["status"] == LocationStatus.PUBLISHED,
                    "avg_rating": float(r["avg_rating"]) if r["avg_rating"] is not None else None,
                    "cover_image": f"{settings.MEDIA_URL_ABS}{r['cover_image']}" if r["cover_image"] else None,
                },
            }
            for r in rows
        ]
        return Response({"type": "FeatureCollection", "features": features})



class AuthorityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Park offices and other managers of campsites, for the "Managed by" dropdown. Public."""

    queryset = Authority.objects.order_by("name")
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None  # a short list
