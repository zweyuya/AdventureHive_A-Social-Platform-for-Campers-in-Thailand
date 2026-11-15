"""Shared helpers for the Django admin."""


class AnnotatedOrderingMixin:
    """Lets a ModelAdmin sort by an annotation. ModelAdmin.get_queryset applies the ordering
    straight away, which fails if the annotation is only added after calling super()."""

    def annotate_queryset(self, queryset):
        return queryset

    def get_queryset(self, request):
        queryset = self.annotate_queryset(self.model._default_manager.get_queryset())
        ordering = self.get_ordering(request)
        return queryset.order_by(*ordering) if ordering else queryset
