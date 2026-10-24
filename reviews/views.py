from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from locations.models import Location

from . import services
from .models import Review, ReviewStatus
from .serializers import ReviewCreateSerializer, ReviewSerializer, ReviewUpdateSerializer


class ReviewPagination(PageNumberPagination):
    page_size = 20


@extend_schema(tags=["reviews"])
class ReviewViewSet(mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                    viewsets.GenericViewSet):
    """
    create   — attended participants of a completed trip (within 30 days)
    update   — author (within the review window)
    destroy  — author
    hide / restore — moderators
    mine     — my reviews
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Review.objects.select_related("user__profile", "trip")
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        if self.action in ("partial_update", "update", "destroy", "mine"):
            return qs.filter(user=user) if user.is_authenticated else qs.none()
        return qs.filter(status=ReviewStatus.PUBLISHED)

    def get_permissions(self):
        if self.action == "retrieve":
            return [permissions.AllowAny()]
        if self.action in ("hide", "restore"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return ReviewCreateSerializer
        if self.action in ("update", "partial_update"):
            return ReviewUpdateSerializer
        return ReviewSerializer

    @extend_schema(responses={201: ReviewSerializer})
    def create(self, request, *args, **kwargs):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        review = services.create_review(request.user, data["trip"], data["rating"],
                                        data.get("review_text", ""))
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=ReviewSerializer)
    def partial_update(self, request, *args, **kwargs):
        review = self.get_object()
        if review.user_id != request.user.pk:
            raise PermissionDenied("Only the author can edit this review.")
        serializer = ReviewUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ReviewSerializer(services.update_review(review,
                                                                serializer.validated_data)).data)

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        if review.user_id != request.user.pk:
            raise PermissionDenied("Only the author can delete this review.")
        services.delete_review(review)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=ReviewSerializer)
    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        review = services.set_review_status(self.get_object(), ReviewStatus.HIDDEN)
        return Response(ReviewSerializer(review).data)

    @extend_schema(request=None, responses=ReviewSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        review = services.set_review_status(self.get_object(), ReviewStatus.PUBLISHED)
        return Response(ReviewSerializer(review).data)

    @extend_schema(responses=ReviewSerializer(many=True))
    @action(detail=False, methods=["get"])
    def mine(self, request):
        qs = self.get_queryset().filter(user=request.user).order_by("-created_at")
        return Response(ReviewSerializer(qs, many=True).data)


@extend_schema(tags=["reviews"], parameters=[
    OpenApiParameter("location_pk", OpenApiTypes.INT, OpenApiParameter.PATH,
                     description="Campsite id"),
])
class CampsiteReviewListView(generics.ListAPIView):
    """Published reviews of a campsite, newest first. Every review is from a verified attendee."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = ReviewPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        location = get_object_or_404(Location.objects.published(), pk=self.kwargs["location_pk"])
        return Review.objects.filter(location=location, status=ReviewStatus.PUBLISHED) \
            .select_related("user__profile", "trip").order_by("-created_at")
