import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from trips.serializers import TripListSerializer
from trips.views import visible_trips

from . import services
from .models import CampingGroup, GroupCategory, GroupMember, GroupMemberStatus, PrivacyType
from .permissions import IsGroupAdmin, IsGroupModerator
from .serializers import (
    AddMemberSerializer,
    GroupSerializer,
    GroupWriteSerializer,
    MemberSerializer,
    RoleSerializer,
)

USER_ID = OpenApiParameter("user_id", OpenApiTypes.INT, OpenApiParameter.PATH)


class GroupPagination(PageNumberPagination):
    page_size = 20


class GroupFilter(django_filters.FilterSet):
    category = django_filters.MultipleChoiceFilter(choices=GroupCategory.choices)
    privacy_type = django_filters.ChoiceFilter(choices=PrivacyType.choices)

    class Meta:
        model = CampingGroup
        fields = ["category", "privacy_type"]


@extend_schema(tags=["groups"])
class GroupViewSet(viewsets.ModelViewSet):
    """
    list / retrieve — anyone (private groups are listed, but their members and trips
                      are visible to members only)
    create          — members; creator becomes the group's admin
    update / delete — group admin
    join            — POST join a public group · DELETE leave
    members         — GET member list · POST add a member (admin / co-admin)
    remove / ban    — admin / co-admin (co-admins: ordinary members only) / admin
    role            — admin changes someone's role
    trips           — the group's trips
    mine            — groups I belong to
    """

    pagination_class = GroupPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GroupFilter
    search_fields = ["name", "description"]
    ordering_fields = ["member_count", "created_at", "name"]
    ordering = ["-member_count", "-created_at"]
    queryset = CampingGroup.objects.select_related("created_by__profile")
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "trips") or (
            self.action == "members" and self.request.method == "GET"
        ):
            return [permissions.AllowAny()]
        if self.action in ("update", "partial_update", "destroy", "role", "ban"):
            return [permissions.IsAuthenticated(), IsGroupAdmin()]
        if self.action in ("members", "remove"):  # POST members = add
            return [permissions.IsAuthenticated(), IsGroupModerator()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return GroupWriteSerializer
        return GroupSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated:
            ctx["my_roles"] = dict(GroupMember.objects.filter(
                user=user, status=GroupMemberStatus.ACTIVE).values_list("group_id", "role_in_group"))
        return ctx

    def _out(self, group, code=status.HTTP_200_OK):
        group = self.get_queryset().get(pk=group.pk)
        return Response(GroupSerializer(group, context=self.get_serializer_context()).data,
                        status=code)

    def _can_see_inside(self, group) -> bool:
        user = self.request.user
        return (group.privacy_type == PrivacyType.PUBLIC
                or (user.is_authenticated and user.is_staff)
                or services.active_membership(group, user) is not None)

    # ---- CRUD -------------------------------------------------------------------
    @extend_schema(responses={201: GroupSerializer})
    def create(self, request, *args, **kwargs):
        serializer = GroupWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._out(services.create_group(request.user, serializer.validated_data),
                         status.HTTP_201_CREATED)

    @extend_schema(responses=GroupSerializer)
    def update(self, request, *args, **kwargs):
        group = self.get_object()
        serializer = GroupWriteSerializer(group, data=request.data,
                                          partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        return self._out(services.update_group(group, request.user, serializer.validated_data))

    def destroy(self, request, *args, **kwargs):
        services.delete_group(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- membership -----------------------------------------------------------
    @extend_schema(request=None, responses=MemberSerializer)
    @action(detail=True, methods=["post", "delete"])
    def join(self, request, pk=None):
        """POST = join (public groups only). DELETE = leave."""
        group = self.get_object()
        if request.method == "POST":
            m = services.join(group, request.user)
            return Response(MemberSerializer(m).data, status=status.HTTP_201_CREATED)
        return Response(MemberSerializer(services.leave(group, request.user)).data)

    @extend_schema(methods=["GET"], responses=MemberSerializer(many=True))
    @extend_schema(methods=["POST"], request=AddMemberSerializer,
                   responses={201: MemberSerializer})
    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        """GET active members (private groups: members only). POST add a member (moderators)."""
        group = self.get_object()
        if request.method == "GET":
            if not self._can_see_inside(group):
                raise PermissionDenied("Members of a private group are visible to members only.")
            qs = group.memberships.filter(status=GroupMemberStatus.ACTIVE) \
                .select_related("user__profile").order_by("joined_at")
            return Response(MemberSerializer(qs, many=True).data)
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        m = services.add_member(group, request.user, serializer.validated_data["user"])
        return Response(MemberSerializer(m).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=MemberSerializer, parameters=[USER_ID])
    @action(detail=True, methods=["post"], url_path=r"members/(?P<user_id>\d+)/remove")
    def remove(self, request, pk=None, user_id=None):
        m = services.remove_member(self.get_object(), request.user, int(user_id))
        return Response(MemberSerializer(m).data)

    @extend_schema(request=None, responses=MemberSerializer, parameters=[USER_ID])
    @action(detail=True, methods=["post"], url_path=r"members/(?P<user_id>\d+)/ban")
    def ban(self, request, pk=None, user_id=None):
        m = services.remove_member(self.get_object(), request.user, int(user_id), ban=True)
        return Response(MemberSerializer(m).data)

    @extend_schema(request=RoleSerializer, responses=MemberSerializer, parameters=[USER_ID])
    @action(detail=True, methods=["post"], url_path=r"members/(?P<user_id>\d+)/role")
    def role(self, request, pk=None, user_id=None):
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        m = services.change_role(self.get_object(), request.user, int(user_id),
                                 serializer.validated_data["role"])
        return Response(MemberSerializer(m).data)

    # ---- related ----------------------------------------------------------------
    @extend_schema(responses=TripListSerializer(many=True))
    @action(detail=True, methods=["get"])
    def trips(self, request, pk=None):
        """Upcoming and past trips of the group (private groups: members only)."""
        group = self.get_object()
        if not self._can_see_inside(group):
            raise PermissionDenied("Trips of a private group are visible to members only.")
        qs = visible_trips(request.user).filter(group=group) \
            .select_related("location", "organizer__profile").order_by("start_datetime")
        return Response(TripListSerializer(qs, many=True, context={"request": request}).data)

    @extend_schema(responses=GroupSerializer(many=True))
    @action(detail=False, methods=["get"])
    def mine(self, request):
        qs = self.get_queryset().filter(memberships__user=request.user,
                                        memberships__status=GroupMemberStatus.ACTIVE)
        return Response(GroupSerializer(qs, many=True, context=self.get_serializer_context()).data)

