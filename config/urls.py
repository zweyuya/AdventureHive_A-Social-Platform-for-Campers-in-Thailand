from django.conf import settings
from django.conf.urls.static import static
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
    # Layer 3 — community groups
    path("api/", include("communities.urls")),
    # Layer 4 — trips, RSVP, waitlist, attendance
    path("api/", include("trips.urls")),
    # Layer 5 — verified reviews & Q&A forum
    path("api/", include("reviews.urls")),
    path("api/", include("qa.urls")),
    path("api/", include("notifications.urls")),
    # Newsfeed — group & trip posts, comments, reactions
    path("api/", include("social.urls")),
]

# Uploaded photos. In development Django serves them; in production the web server
# (nginx) serves MEDIA_ROOT at /media/ instead.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
