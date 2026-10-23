from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer("Health", {"status": serializers.CharField()}),
    tags=["system"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness check for deployment: confirms Django is up and PostgreSQL answers."""
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return Response({"status": "ok"})
