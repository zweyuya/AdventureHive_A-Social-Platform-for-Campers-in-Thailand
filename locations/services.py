"""
Campsite content workflow.

Submission:   draft ──submit──▶ pending_review ──approve──▶ published (version 1)
                 ▲                     │
                 └──── edit/resubmit ◀─┴──reject (note required)──▶ rejected

Suggested edit to a published campsite:
              pending revision ──approve──▶ applied as version N+1
                               └─reject (note)──▶ rejected revision

Every approved change is stored in location_revisions (full history: who,
when, what, and the complete snapshot), so any version can be inspected.
All transitions run in one transaction with the campsite row locked.

Every pin that is saved must be inside Thailand and match its province
(check_pin_and_province, using the province boundaries in core/provinces.py).
"""
from math import cos, radians

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.provinces import canonical_province, check_pin, distance_km
from notifications.models import NotificationType, ReferenceType
from notifications.services import notify

from .models import Location, LocationRevision, LocationStatus, PermitStatus, RevisionStatus

# Fields that users may write and that are captured in every version snapshot.
EDITABLE_FIELDS = [
    "name", "province", "latitude", "longitude", "category", "description",
    "terrain_type", "elevation_m", "has_water_source", "has_restrooms",
    "fire_pit_allowed", "site_capacity", "authority_id", "permit_status",
    "permit_details", "fees", "permit_booking_url", "rules", "permit_info_source",
]

# Changing any of these means the permit information was (re)checked by a moderator.
PERMIT_FIELDS = ["authority_id", "permit_status", "permit_details", "fees",
                 "permit_booking_url", "rules", "permit_info_source"]


class WorkflowError(ValidationError):
    """A transition that is not allowed from the current state (HTTP 400)."""


# --------------------------------------------------------------------------
# Map pin checks
# --------------------------------------------------------------------------
PIN_FIELDS = ("latitude", "longitude", "province")
NEARBY_KM = 1.0


def check_pin_and_province(values: dict, current: Location | None = None) -> dict:
    """
    The pin must be inside Thailand and the province must match it; a blank
    province is filled in from the pin. Returns `values` with the province
    spelled canonically. Skipped when an edit does not touch the pin or province.
    """
    if current is not None and not any(k in values for k in PIN_FIELDS):
        return values

    def get(key):
        return values[key] if key in values else getattr(current, key, None)

    lat, lng = get("latitude"), get("longitude")
    if lat is None or lng is None:
        return values  # field validation reports the missing pin
    pin = check_pin(lat, lng)
    if not pin.in_thailand:
        where = f"in {pin.country}" if pin.country else "outside Thailand"
        raise ValidationError({"latitude": [f"This pin is {where}. Campsites must be inside Thailand."]})

    typed = (get("province") or "").strip()
    if not typed:
        values["province"] = pin.province
        return values
    name = canonical_province(typed)
    if name is None:
        raise ValidationError({"province": [f"'{typed}' is not a Thai province."]})
    if name not in pin.allowed:
        raise ValidationError({"province": [f"The pin is in {pin.province}, not {name}. "
                                            f"Move the pin or change the province."]})
    values["province"] = name
    return values


def pin_problem(location: Location) -> str | None:
    """Why this saved pin must not be published (it was valid when saved; the check runs again)."""
    pin = check_pin(location.latitude, location.longitude)
    if not pin.in_thailand:
        return f"The pin is {f'in {pin.country}' if pin.country else 'outside Thailand'}."
    name = canonical_province(location.province)
    if name not in pin.allowed:
        return f"The pin is in {pin.province}, not {location.province}."
    return None


def nearby_campsites(latitude: float, longitude: float, km: float = NEARBY_KM,
                     queryset=None, exclude_id=None) -> list[tuple[Location, float]]:
    """Campsites within `km` of a point, nearest first — to spot duplicate submissions."""
    pad_lat = km / 111.0
    pad_lng = pad_lat / max(cos(radians(latitude)), 0.1)
    qs = (queryset if queryset is not None else Location.objects.all()).filter(
        latitude__range=(latitude - pad_lat, latitude + pad_lat),
        longitude__range=(longitude - pad_lng, longitude + pad_lng),
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    found = [(loc, distance_km(latitude, longitude, loc.latitude, loc.longitude)) for loc in qs]
    return sorted([(loc, d) for loc, d in found if d <= km], key=lambda pair: pair[1])


def snapshot(location: Location) -> dict:
    return {f: getattr(location, f) for f in EDITABLE_FIELDS}


def _lock(location: Location) -> Location:
    return Location.objects.select_for_update().get(pk=location.pk)


def _next_version(location: Location) -> int:
    top = location.revisions.aggregate(m=Max("version_no"))["m"] or 0
    return max(top, location.current_version) + 1


def _record_version(location, edited_by, reviewed_by, summary) -> LocationRevision:
    version = _next_version(location)
    rev = LocationRevision.objects.create(
        location=location, version_no=version, snapshot=snapshot(location),
        edit_summary=summary[:300], edited_by=edited_by, reviewed_by=reviewed_by,
        status=RevisionStatus.APPROVED,
    )
    location.current_version = version
    location.save(update_fields=["current_version", "updated_at"])
    return rev


# --------------------------------------------------------------------------
# New campsite submissions
# --------------------------------------------------------------------------
@transaction.atomic
def submit(location: Location, user) -> Location:
    location = _lock(location)
    if location.created_by_id != user.pk:
        raise WorkflowError("Only the submitter can submit this campsite.")
    if location.status not in (LocationStatus.DRAFT, LocationStatus.REJECTED):
        raise WorkflowError(f"A {location.status} campsite cannot be submitted.")
    location.status = LocationStatus.PENDING_REVIEW
    location.save(update_fields=["status", "updated_at"])
    return location


@transaction.atomic
def approve_submission(location: Location, moderator) -> Location:
    location = _lock(location)
    if location.status != LocationStatus.PENDING_REVIEW:
        raise WorkflowError("Only campsites pending review can be approved.")
    if problem := pin_problem(location):
        raise WorkflowError(f"This campsite cannot be approved. {problem}")
    location.status = LocationStatus.PUBLISHED
    location.reviewed_by = moderator
    location.reviewed_at = timezone.now()
    if location.permit_status != PermitStatus.UNKNOWN:  # nothing to check while it's "I don't know"
        location.permit_info_verified_at = location.reviewed_at
    location.moderation_note = ""
    location.save()
    _record_version(location, location.created_by, moderator, "Initial submission approved")
    notify(location.created_by, NotificationType.SUBMISSION_APPROVED,
           ReferenceType.LOCATION, location.pk, actor=moderator)
    return location


@transaction.atomic
def reject_submission(location: Location, moderator, note: str) -> Location:
    note = (note or "").strip()
    if not note:
        raise WorkflowError({"note": "A reason is required when rejecting."})
    location = _lock(location)
    if location.status != LocationStatus.PENDING_REVIEW:
        raise WorkflowError("Only campsites pending review can be rejected.")
    location.status = LocationStatus.REJECTED
    location.reviewed_by = moderator
    location.reviewed_at = timezone.now()
    location.moderation_note = note
    location.save()
    notify(location.created_by, NotificationType.SUBMISSION_REJECTED,
           ReferenceType.LOCATION, location.pk, actor=moderator)
    return location


# --------------------------------------------------------------------------
# Suggested edits to published campsites
# --------------------------------------------------------------------------
@transaction.atomic
def propose_edit(location: Location, user, changes: dict, summary: str) -> LocationRevision:
    location = _lock(location)
    if location.status != LocationStatus.PUBLISHED:
        raise WorkflowError("Edits can only be suggested for published campsites.")
    changes = check_pin_and_province(dict(changes), location)
    proposed = snapshot(location)
    proposed.update({k: v for k, v in changes.items() if k in EDITABLE_FIELDS})
    if proposed == snapshot(location):
        raise WorkflowError("The suggestion does not change anything.")
    proposed["_base_version"] = location.current_version
    return LocationRevision.objects.create(
        location=location, snapshot=proposed, edit_summary=summary[:300],
        edited_by=user, status=RevisionStatus.PENDING,
    )


@transaction.atomic
def approve_revision(revision: LocationRevision, moderator) -> LocationRevision:
    revision = LocationRevision.objects.select_for_update().get(pk=revision.pk)
    if revision.status != RevisionStatus.PENDING:
        raise WorkflowError("Only pending suggestions can be approved.")
    location = _lock(revision.location)
    base = revision.snapshot.get("_base_version")
    if base is not None and base != location.current_version:
        raise WorkflowError(
            f"This suggestion was made on version {base}, but the campsite is now on "
            f"version {location.current_version}. Reject it and ask for a new suggestion."
        )
    before = snapshot(location)
    for field in EDITABLE_FIELDS:
        if field in revision.snapshot:
            setattr(location, field, revision.snapshot[field])
    if location.permit_status == PermitStatus.UNKNOWN:
        location.permit_info_verified_at = None  # back to "haven't been verified yet"
    elif any(getattr(location, f) != before[f] for f in PERMIT_FIELDS):
        location.permit_info_verified_at = timezone.now()
    try:
        location.full_clean(exclude=["avg_rating", "embedding"])
    except DjangoValidationError as exc:
        raise WorkflowError(exc.message_dict) from exc
    location.save()

    version = _next_version(location)
    revision.status = RevisionStatus.APPROVED
    revision.version_no = version
    revision.reviewed_by = moderator
    revision.snapshot = snapshot(location)
    revision.save()
    location.current_version = version
    location.save(update_fields=["current_version", "updated_at"])
    notify(revision.edited_by, NotificationType.SUBMISSION_APPROVED,
           ReferenceType.LOCATION, location.pk, actor=moderator)
    return revision


@transaction.atomic
def reject_revision(revision: LocationRevision, moderator, note: str) -> LocationRevision:
    note = (note or "").strip()
    if not note:
        raise WorkflowError({"note": "A reason is required when rejecting."})
    revision = LocationRevision.objects.select_for_update().get(pk=revision.pk)
    if revision.status != RevisionStatus.PENDING:
        raise WorkflowError("Only pending suggestions can be rejected.")
    revision.status = RevisionStatus.REJECTED
    revision.reviewed_by = moderator
    revision.review_note = note
    revision.save()
    notify(revision.edited_by, NotificationType.SUBMISSION_REJECTED,
           ReferenceType.LOCATION, revision.location_id, actor=moderator)
    return revision


# --------------------------------------------------------------------------
# Direct edits by staff in the Django admin (still versioned)
# --------------------------------------------------------------------------
@transaction.atomic
def record_admin_edit(location: Location, moderator, changed_fields) -> LocationRevision | None:
    changed = [f for f in changed_fields if f in EDITABLE_FIELDS or f"{f}_id" in EDITABLE_FIELDS]
    if location.status != LocationStatus.PUBLISHED or not changed:
        return None
    location = _lock(location)
    return _record_version(location, moderator, moderator,
                           f"Edited by moderator: {', '.join(sorted(changed))}")
