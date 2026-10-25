import django_filters

from .models import Location, LocationCategory, PermitStatus


class CampsiteFilter(django_filters.FilterSet):
    province = django_filters.CharFilter(lookup_expr="iexact")
    category = django_filters.MultipleChoiceFilter(choices=LocationCategory.choices)
    permit_status = django_filters.ChoiceFilter(choices=PermitStatus.choices)
    has_water_source = django_filters.BooleanFilter()
    has_restrooms = django_filters.BooleanFilter()
    fire_pit_allowed = django_filters.BooleanFilter()
    min_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte",
                                             help_text="Minimum average rating (1–5).")
    has_photo = django_filters.BooleanFilter(method="filter_has_photo",
                                             help_text="true = only campsites with a cover photo")

    class Meta:
        model = Location
        fields = ["province", "category", "permit_status", "has_water_source",
                  "has_restrooms", "fire_pit_allowed", "min_rating", "has_photo"]

    def filter_has_photo(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.exclude(cover_image="") if value else queryset.filter(cover_image="")
