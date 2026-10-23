"""Thailand bounding box, used by model validators and DB check constraints."""
from django.core.exceptions import ValidationError
from django.db.models import Q

TH_LAT_MIN, TH_LAT_MAX = 5.6, 20.5
TH_LNG_MIN, TH_LNG_MAX = 97.3, 105.7


def validate_th_latitude(value):
    if value is not None and not (TH_LAT_MIN <= value <= TH_LAT_MAX):
        raise ValidationError(f"Latitude must be within Thailand ({TH_LAT_MIN}–{TH_LAT_MAX}).")


def validate_th_longitude(value):
    if value is not None and not (TH_LNG_MIN <= value <= TH_LNG_MAX):
        raise ValidationError(f"Longitude must be within Thailand ({TH_LNG_MIN}–{TH_LNG_MAX}).")


def in_thailand_q(lat_field: str, lng_field: str) -> Q:
    """Q object for a CheckConstraint that keeps coordinates inside Thailand."""
    return Q(
        **{
            f"{lat_field}__gte": TH_LAT_MIN,
            f"{lat_field}__lte": TH_LAT_MAX,
            f"{lng_field}__gte": TH_LNG_MIN,
            f"{lng_field}__lte": TH_LNG_MAX,
        }
    )
