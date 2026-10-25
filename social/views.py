from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from communities.models import (CampingGroup, GroupMember, GroupMemberStatus, PrivacyType)
from core.images import process_photo
from trips.models import Trip

from . import services
from .models import Comment, ContentStatus, Post, PostStatus
from .serializers import (CommentCreateSerializer, CommentSerializer, PostCreateSerializer,
                          PostEditSerializer, PostSerializer, ReactSerializer, RejectPostSerializer)


class PostPagination(PageNumberPagination):
    page_size = 20


@extend_schema(tags=["feed"], parameters=[
    OpenApiParameter("group", OpenApiTypes.INT, description="Posts in this group"),
    OpenApiParameter("trip", OpenApiTypes.INT, description="Posts on this trip"),
    OpenApiParameter("status", OpenApiTypes.STR,
                     description="pending_review = approval queue (group moderators only)"),
])
class PostViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """
    list      — ?group=ID (group posts) · ?trip=ID (trip posts) · no filter = my home feed
                (posts from my groups and trips). ?group=ID&status=pending_review = approval queue.
    create    — multipart or JSON: content_text, group_id OR trip_id, optional image.
                Private-group posts by members start as pending_review.
    update    — author edits the text (private-group posts go back for approval)
    destroy   — author or moderator
    approve / reject — group admins & co-admins (reject needs a note)
    hide / restore   — moderators of the group/trip
    react     — PUT {"type": "like|love|haha|wow|sad"} · DELETE removes your reaction
    comments  — GET thread · POST {"content_text", "parent_comment_id"?}
    """

    pagination_class = PostPagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    serializer_class = PostSerializer

    def _base(self):
        return Post.objects.select_related("user__profile", "group", "trip")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Post.objects.none()
        user = self.request.user
        qs = services.visible_posts(user, self._base())
        if self.action != "list":
            return qs
        params = self.request.query_params
        group_id, trip_id = params.get("group"), params.get("trip")
        if group_id:
            group = get_object_or_404(CampingGroup, pk=group_id)
            if group.privacy_type == PrivacyType.PRIVATE and not (
                user.is_authenticated and (user.is_staff or services.group_role(group, user))):
                raise PermissionDenied("Posts in a private group are visible to members only.")
            qs = qs.filter(group=group)
            if params.get("status") == PostStatus.PENDING_REVIEW:
                if not services.can_moderate_place(user, group=group):
                    raise PermissionDenied("Only group admins and co-admins can see the approval queue.")
                return qs.filter(status=PostStatus.PENDING_REVIEW).order_by("created_at")
        elif trip_id:
            trip = get_object_or_404(Trip, pk=trip_id)
            if not (user.is_authenticated and (user.is_staff or services.is_trip_member(trip, user))):
                raise PermissionDenied("Trip posts are visible to the organizer and people going.")
            qs = qs.filter(trip=trip)
        else:
            if not user.is_authenticated:
                raise NotAuthenticated("Log in to see your feed.")
            return services.feed_for(user, self._base()).order_by("-created_at")
        # In a place: published posts, plus my own pending/rejected ones.
        from django.db.models import Q
        return qs.filter(Q(status=PostStatus.PUBLISHED) | Q(user=user if user.is_authenticated else None)) \
            .order_by("-created_at")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "comments") and self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated:
            ctx["moderated_groups"] = set(GroupMember.objects.filter(
                user=user, status=GroupMemberStatus.ACTIVE,
                role_in_group__in=services.MODERATOR_ROLES).values_list("group_id", flat=True))
        return ctx

    def _serialize(self, posts, many=False):
        posts_list = list(posts) if many else [posts]
        summary, mine = services.reaction_summaries([p.pk for p in posts_list], self.request.user)
        ctx = {**self.get_serializer_context(), "reaction_summary": summary, "my_reactions": mine}
        return PostSerializer(posts if many else posts_list[0], many=many, context=ctx).data

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self._serialize(page, many=True))

    def retrieve(self, request, *args, **kwargs):
        return Response(self._serialize(self.get_object()))

    def _fresh(self, post, code=status.HTTP_200_OK):
        return Response(self._serialize(self._base().get(pk=post.pk)), status=code)

    @extend_schema(request={"multipart/form-data": PostCreateSerializer,
                            "application/json": PostCreateSerializer},
                   responses={201: PostSerializer})
    def create(self, request, *args, **kwargs):
        s = PostCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        image = process_photo(d["image"], field="image") if d.get("image") else None
        post = services.create_post(request.user, content_text=d.get("content_text", ""),
                                    group=d.get("group"), trip=d.get("trip"), image=image)
        return self._fresh(post, status.HTTP_201_CREATED)

    @extend_schema(request=PostEditSerializer, responses=PostSerializer)
    def update(self, request, *args, **kwargs):
        s = PostEditSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._fresh(services.edit_post(self.get_object(), request.user, s.validated_data["content_text"]))

    def destroy(self, request, *args, **kwargs):
        services.delete_post(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=PostSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._fresh(services.review_post(self.get_object(), request.user, approve=True))

    @extend_schema(request=RejectPostSerializer, responses=PostSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        s = RejectPostSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._fresh(services.review_post(self.get_object(), request.user, approve=False,
                                                note=s.validated_data["note"]))

    @extend_schema(request=None, responses=PostSerializer)
    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        return self._fresh(services.set_post_hidden(self.get_object(), request.user, True))

    @extend_schema(request=None, responses=PostSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        return self._fresh(services.set_post_hidden(self.get_object(), request.user, False))

    @extend_schema(request=ReactSerializer, responses=PostSerializer)
    @action(detail=True, methods=["put", "delete"])
    def react(self, request, pk=None):
        post = self.get_object()
        if request.method == "PUT":
            s = ReactSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            services.react(post, request.user, s.validated_data["type"])
        else:
            services.unreact(post, request.user)
        return self._fresh(post)

    @extend_schema(methods=["GET"], responses=CommentSerializer(many=True))
    @extend_schema(methods=["POST"], request=CommentCreateSerializer, responses={201: CommentSerializer})
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == "POST":
            s = CommentCreateSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            c = services.add_comment(post, request.user, s.validated_data["content_text"],
                                     s.validated_data.get("parent_comment_id"))
            return Response(CommentSerializer(c, context={"request": request}).data,
                            status=status.HTTP_201_CREATED)
        can_mod = services.can_moderate(request.user, post)
        qs = post.comments.select_related("user__profile")
        if not can_mod:
            qs = qs.filter(status=ContentStatus.PUBLISHED)
        comments = list(qs)
        replies = {}
        for c in comments:
            if c.parent_comment_id:
                replies.setdefault(c.parent_comment_id, []).append(c)
        top = [c for c in comments if not c.parent_comment_id]
        ctx = {"request": request, "replies": replies, "can_moderate": can_mod}
        return Response(CommentSerializer(top, many=True, context=ctx).data)


@extend_schema(tags=["feed"])
class CommentViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Delete your comment (or moderate one); moderators hide / restore comments."""

    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.select_related("post__group", "post__trip")
    serializer_class = CommentSerializer

    def destroy(self, request, *args, **kwargs):
        services.delete_comment(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=CommentSerializer)
    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        c = services.set_comment_hidden(self.get_object(), request.user, True)
        return Response(CommentSerializer(c, context={"request": request}).data)

    @extend_schema(request=None, responses=CommentSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        c = services.set_comment_hidden(self.get_object(), request.user, False)
        return Response(CommentSerializer(c, context={"request": request}).data)
