import django_filters
from django.db.models import F

from core.models import ExperienceLevel

from .models import DifficultyLevel, Trip, TripStatus


class TripFilter(django_filters.FilterSet):
    location = django_filters.NumberFilter(field_name="location_id")
    province = django_filters.CharFilter(field_name="location__province", lookup_expr="iexact")
    status = django_filters.MultipleChoiceFilter(choices=TripStatus.choices)
    difficulty = django_filters.MultipleChoiceFilter(choices=DifficultyLevel.choices)
    min_experience_level = django_filters.ChoiceFilter(choices=ExperienceLevel.choices)
    start_after = django_filters.IsoDateTimeFilter(field_name="start_datetime", lookup_expr="gte")
    start_before = django_filters.IsoDateTimeFilter(field_name="start_datetime", lookup_expr="lte")
    has_spots = django_filters.BooleanFilter(method="filter_has_spots",
                                             help_text="true = at least one seat left")

    class Meta:
        model = Trip
        fields = ["location", "province", "status", "difficulty", "min_experience_level",
                  "start_after", "start_before", "has_spots"]

    def filter_has_spots(self, queryset, name, value):
        if value is None:
            return queryset
        lookup = queryset.filter if value else queryset.exclude
        return lookup(confirmed_count__lt=F("participant_capacity"))
