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
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.models import NotificationType, ReferenceType
from notifications.services import notify

from .models import Location, LocationRevision, LocationStatus, RevisionStatus

# Fields that users may write and that are captured in every version snapshot.
EDITABLE_FIELDS = [
    "name", "province", "latitude", "longitude", "category", "description",
    "terrain_type", "elevation_m", "has_water_source", "has_restrooms",
    "fire_pit_allowed", "site_capacity", "authority_id", "permit_status",
    "permit_details", "permit_booking_url", "rules", "permit_info_source",
]


class WorkflowError(ValidationError):
    """A transition that is not allowed from the current state (HTTP 400)."""


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
    location.status = LocationStatus.PUBLISHED
    location.reviewed_by = moderator
    location.reviewed_at = timezone.now()
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
    for field in EDITABLE_FIELDS:
        if field in revision.snapshot:
            setattr(location, field, revision.snapshot[field])
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
