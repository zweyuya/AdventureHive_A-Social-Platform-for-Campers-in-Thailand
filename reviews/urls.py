from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CampsiteReviewListView, ReviewViewSet

router = DefaultRouter(trailing_slash=True)
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("campsites/<int:location_pk>/reviews/", CampsiteReviewListView.as_view(),
         name="campsite-reviews"),
    *router.urls,
]
