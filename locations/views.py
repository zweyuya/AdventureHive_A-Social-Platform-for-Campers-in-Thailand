from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .filters import CampsiteFilter
from .models import Location, LocationRevision, LocationStatus, RevisionStatus
from .serializers import (
    CampsiteDetailSerializer,
    CampsiteListSerializer,
    CampsiteWriteSerializer,
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

    list / retrieve     — anyone; only published campsites (submitters also see their own)
    create              — members; creates a DRAFT (not public)
    update / partial    — the submitter, only while draft or rejected
    submit              — the submitter: draft/rejected → pending_review
    approve / reject    — staff: pending_review → published / rejected (note required)
    mine                — the member's own submissions with their status
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
            return qs.published()
        if self.action in ("approve", "reject"):
            return qs  # staff only, see get_permissions
        if user.is_authenticated and user.is_staff:
            return qs
        if user.is_authenticated:
            return qs.filter(Q(status=LocationStatus.PUBLISHED) | Q(created_by=user))
        return qs.published()

    def get_permissions(self):
        if self.action in ("list", "retrieve", "history"):
            return [permissions.AllowAny()]
        if self.action in ("approve", "reject"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

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
        location = get_object_or_404(Location.objects.published(), pk=pk)
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
    Lightweight GeoJSON for the map (published campsites only, no pagination).
    Accepts the same filters as the list.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = CampsiteFilter(request.GET, queryset=Location.objects.published()).qs
        rows = qs.values("id", "name", "category", "province", "avg_rating",
                         "latitude", "longitude", "cover_image")
        features = [
            {
                "type": "Feature",
                # GeoJSON order is [longitude, latitude]
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "id": r["id"], "name": r["name"], "category": r["category"],
                    "province": r["province"],
                    "avg_rating": float(r["avg_rating"]) if r["avg_rating"] is not None else None,
                    "cover_image": f"{settings.MEDIA_URL_ABS}{r['cover_image']}" if r["cover_image"] else None,
                },
            }
            for r in rows
        ]
        return Response({"type": "FeatureCollection", "features": features})

