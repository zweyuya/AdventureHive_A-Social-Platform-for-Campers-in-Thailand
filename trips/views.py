from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django_filters.rest_framework import DjangoFilterBackend

from communities.models import GroupMember

from . import services
from .filters import TripFilter
from .models import Trip, TripEquipmentItem, TripParticipant, TripStatus
from .permissions import IsOrganizer, IsOrganizerOrStaff
from .serializers import (
    AttendanceSerializer,
    EquipmentSerializer,
    ParticipantSerializer,
    RsvpResultSerializer,
    TripDetailSerializer,
    TripListSerializer,
    TripWriteSerializer,
)


class TripPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def visible_trips(user, qs=None):
    """
    Drafts: organizer only. Trips in a private group: active members (and the
    organizer) only. Staff see everything.
    """
    qs = qs if qs is not None else Trip.objects.all()
    if user.is_authenticated and user.is_staff:
        return qs
    visible = ~Q(status=TripStatus.DRAFT)
    if user.is_authenticated:
        visible |= Q(organizer=user)
    qs = qs.filter(visible)
    private = Q(group__privacy_type="private")
    if user.is_authenticated:
        is_member = Exists(GroupMember.objects.filter(
            group=OuterRef("group"), user=user, status="active"))
        return qs.filter(~private | Q(organizer=user) | Q(is_member))
    return qs.filter(~private | Q(group__isnull=True))


@extend_schema(tags=["trips"])
class TripViewSet(viewsets.ModelViewSet):
    """
    list        — anyone. Default: upcoming published/full trips. Pass ?status=... to see others.
    retrieve    — anyone (drafts only for the organizer). Exact meeting point only for
                  the organizer and confirmed participants.
    create      — members; creates a DRAFT
    update      — organizer
    destroy     — organizer or moderator: CANCELS the trip (never deleted)
    publish     — organizer: draft → published
    rsvp        — POST join (confirmed or waitlisted), DELETE leave (waitlist #1 promoted)
    participants— organizer only
    attendance  — organizer, after completion: mark attended / no_show
    mine        — trips I organise or joined
    """

    pagination_class = TripPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TripFilter
    search_fields = ["title", "location__name", "location__province"]
    ordering_fields = ["start_datetime", "created_at"]
    ordering = ["start_datetime"]
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        qs = visible_trips(self.request.user, Trip.objects.select_related(
            "location", "organizer__profile", "group").prefetch_related("equipment_items"))
        if self.action == "list":
            qs = qs.exclude(status=TripStatus.DRAFT)
            if "status" not in self.request.query_params:
                qs = qs.filter(status__in=services.OPEN_STATUSES,
                               start_datetime__gte=timezone.now())
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action in ("update", "partial_update", "publish", "participants", "attendance"):
            return [permissions.IsAuthenticated(), IsOrganizer()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsOrganizerOrStaff()]
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action == "rsvp":  # RSVP-flooding protection
            self.throttle_scope = "rsvp"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        return {
            "list": TripListSerializer,
            "mine": TripListSerializer,
            "create": TripWriteSerializer,
            "update": TripWriteSerializer,
            "partial_update": TripWriteSerializer,
            "participants": ParticipantSerializer,
            "attendance": AttendanceSerializer,
            "rsvp": RsvpResultSerializer,
        }.get(self.action, TripDetailSerializer)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated:
            ctx["my_rsvps"] = {
                t: (s, p) for t, s, p in TripParticipant.objects.filter(user=user)
                .values_list("trip_id", "status", "waitlist_position")
            }
        return ctx

    def _detail(self, trip, code=status.HTTP_200_OK):
        trip = self.get_queryset().get(pk=trip.pk)
        return Response(TripDetailSerializer(trip, context=self.get_serializer_context()).data,
                        status=code)

    # ---- CRUD -------------------------------------------------------------------
    @extend_schema(responses={201: TripDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trip = serializer.save(organizer=request.user, status=TripStatus.DRAFT)
        return self._detail(trip, status.HTTP_201_CREATED)

    @extend_schema(responses=TripDetailSerializer)
    def update(self, request, *args, **kwargs):
        trip = self.get_object()
        serializer = self.get_serializer(trip, data=request.data,
                                         partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        return self._detail(serializer.save())

    @extend_schema(request=None, responses=TripDetailSerializer,
                   description="Cancels the trip (status → cancelled). Trips are never deleted.")
    def destroy(self, request, *args, **kwargs):
        return self._detail(services.cancel_trip(self.get_object(), request.user))

    # ---- lifecycle ----------------------------------------------------------------
    @extend_schema(request=None, responses=TripDetailSerializer)
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        return self._detail(services.publish(self.get_object()))

    @extend_schema(request=None, responses=RsvpResultSerializer)
    @action(detail=True, methods=["post", "delete"])
    def rsvp(self, request, pk=None):
        """POST = join (confirmed if a seat is free, otherwise waitlisted). DELETE = leave."""
        trip = self.get_object()
        if request.method == "POST":
            participant = services.rsvp(trip, request.user)
            return Response(RsvpResultSerializer(participant).data, status=status.HTTP_201_CREATED)
        participant = services.cancel_rsvp(trip, request.user)
        return Response(RsvpResultSerializer(participant).data)

    @extend_schema(responses=ParticipantSerializer(many=True))
    @action(detail=True, methods=["get"])
    def participants(self, request, pk=None):
        trip = self.get_object()
        qs = trip.participants.select_related("user__profile").order_by(
            "status", "waitlist_position", "joined_at")
        return Response(ParticipantSerializer(qs, many=True).data)

    @extend_schema(request=AttendanceSerializer, responses=ParticipantSerializer(many=True))
    @action(detail=True, methods=["post"])
    def attendance(self, request, pk=None):
        trip = self.get_object()
        serializer = AttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.mark_attendance(trip, request.user, serializer.validated_data["records"])
        return Response(ParticipantSerializer(updated, many=True).data)

    @extend_schema(responses=TripListSerializer(many=True))
    @action(detail=False, methods=["get"])
    def mine(self, request):
        """Trips I organise or have joined (any status), soonest first."""
        user = request.user
        qs = Trip.objects.filter(Q(organizer=user) | Q(participants__user=user)).distinct() \
            .select_related("location", "organizer__profile").order_by("start_datetime")
        return Response(TripListSerializer(qs, many=True,
                                           context=self.get_serializer_context()).data)


@extend_schema(tags=["trips"], parameters=[
    OpenApiParameter("trip_pk", OpenApiTypes.INT, OpenApiParameter.PATH),
])
class EquipmentViewSet(viewsets.ModelViewSet):
    """Equipment list of a trip. Anyone who can see the trip can read it; the organizer edits."""

    serializer_class = EquipmentSerializer
    pagination_class = None
    queryset = TripEquipmentItem.objects.none()

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_trip(self):
        if not hasattr(self, "_trip"):
            self._trip = get_object_or_404(visible_trips(self.request.user),
                                           pk=self.kwargs["trip_pk"])
        return self._trip

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TripEquipmentItem.objects.none()
        return self.get_trip().equipment_items.all()

    def _check_organizer(self):
        trip = self.get_trip()
        if trip.organizer_id != self.request.user.pk:
            raise PermissionDenied("Only the trip organizer can change the equipment list.")
        if trip.status in (TripStatus.CANCELLED, TripStatus.COMPLETED):
            raise ValidationError(f"The equipment list of a {trip.status} trip cannot change.")

    def perform_create(self, serializer):
        self._check_organizer()
        serializer.save(trip=self.get_trip())

    def perform_update(self, serializer):
        self._check_organizer()
        serializer.save()

    def perform_destroy(self, instance):
        self._check_organizer()
        instance.delete()
