from rest_framework.routers import DefaultRouter

from .views import EquipmentViewSet, TripViewSet

router = DefaultRouter(trailing_slash=True)
router.register("trips", TripViewSet, basename="trip")
router.register(r"trips/(?P<trip_pk>\d+)/equipment", EquipmentViewSet, basename="trip-equipment")

urlpatterns = router.urls
