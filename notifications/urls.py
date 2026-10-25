from django.urls import path

from .views import mark_all_read, notification_list

urlpatterns = [
    path("notifications/", notification_list, name="notifications"),
    path("notifications/read-all/", mark_all_read, name="notifications-read-all"),
]
