from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    """20 items per page, stable cursor ordering (newest first)."""

    page_size = 20
    ordering = "-id"
