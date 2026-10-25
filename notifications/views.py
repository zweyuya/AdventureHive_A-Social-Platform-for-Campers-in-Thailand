from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from locations.models import Location
from qa.models import Question
from trips.models import Trip

from .models import Notification, ReferenceType
from .serializers import NotificationSerializer

_NAME_SOURCES = {
    ReferenceType.TRIP: (Trip, "title"),
    ReferenceType.LOCATION: (Location, "name"),
    ReferenceType.QUESTION: (Question, "title"),
}


def _names(notifications) -> dict:
    """Look up titles for all referenced objects in one query per type."""
    out = {}
    for ref_type, (model, field) in _NAME_SOURCES.items():
        ids = {n.reference_id for n in notifications if n.reference_type == ref_type}
        for pk, name in model.objects.filter(pk__in=ids).values_list("pk", field):
            out[(ref_type, pk)] = name
    return out


@extend_schema(
    tags=["notifications"],
    responses=inline_serializer("NotificationList", {
        "unread_count": serializers.IntegerField(),
        "results": NotificationSerializer(many=True),
    }),
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def notification_list(request):
    """My latest 30 notifications and the number of unread ones."""
    qs = Notification.objects.filter(recipient=request.user)
    latest = list(qs.select_related("actor__profile").order_by("-created_at")[:30])
    post_ids = [n.reference_id for n in latest if n.reference_type == ReferenceType.POST]
    from social.models import Post
    post_groups = {pk: name or "a trip" for pk, name in
                   Post.objects.filter(pk__in=post_ids).values_list("pk", "group__name")}
    data = NotificationSerializer(latest, many=True,
                                  context={"names": _names(latest), "post_groups": post_groups}).data
    return Response({"unread_count": qs.filter(is_read=False).count(), "results": data})


@extend_schema(tags=["notifications"], request=None,
               responses=inline_serializer("MarkedRead", {"marked": serializers.IntegerField()}))
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_all_read(request):
    marked = Notification.objects.filter(recipient=request.user, is_read=False) \
        .update(is_read=True)
    return Response({"marked": marked})
