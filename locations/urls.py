from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CampsiteMapView, CampsiteViewSet, RevisionModerationViewSet

router = DefaultRouter(trailing_slash=True)
router.register("campsites", CampsiteViewSet, basename="campsite")
router.register("campsite-revisions", RevisionModerationViewSet, basename="campsite-revision")

urlpatterns = [
    path("map/campsites/", CampsiteMapView.as_view(), name="map-campsites"),
    *router.urls,
]
