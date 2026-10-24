from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts.urls import auth_urlpatterns, users_urlpatterns
from accounts.views import InterestTagListView
from core.views import health

admin.site.site_header = "AdventureHive admin"
admin.site.site_title = "AdventureHive admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Layer 1 — auth & profiles
    path("api/auth/", include(auth_urlpatterns)),
    path("api/users/", include(users_urlpatterns)),
    path("api/interest-tags/", InterestTagListView.as_view(), name="interest-tags"),
    # Layer 2 — campsites & content workflow
    path("api/", include("locations.urls")),
    # Layer 4 — trips, RSVP, waitlist, attendance
    path("api/", include("trips.urls")),
]
