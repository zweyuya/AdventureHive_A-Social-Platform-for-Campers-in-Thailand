from django.contrib import admin, messages
from django.db.models import Case, IntegerField, Value, When
from rest_framework.exceptions import ValidationError

from core.admin_helpers import AnnotatedOrderingMixin
from locations.admin import _reject_with_note, _run
from reviews import services as review_services

from . import services
from .models import (
    AppealStatus,
    AttendanceAppeal,
    EmergencyContactAccess,
    Trip,
    TripEquipmentItem,
    TripParticipant,
)


class EquipmentInline(admin.TabularInline):
    model = TripEquipmentItem
    extra = 0


class ParticipantInline(admin.TabularInline):
    """Read-only: seats and the waitlist must change only through the RSVP rules."""

    model = TripParticipant
    fk_name = "trip"
    extra = 0
    can_delete = False
    fields = ("user", "status", "waitlist_position", "joined_at", "checked_in_at",
              "verification_method", "override_reason", "attendance_marked_by",
              "attendance_marked_at", "share_emergency_contact")
    readonly_fields = fields
    ordering = ("status", "waitlist_position", "joined_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "organizer", "status", "start_datetime",
                    "confirmed_count", "participant_capacity", "flag_status")
    list_filter = ("flag_status", "status", "difficulty", "members_only")
    search_fields = ("title", "location__name")
    raw_id_fields = ("organizer", "location", "group")
    readonly_fields = ("status", "confirmed_count", "created_at", "updated_at",
                       "flag_status", "flag_note", "flagged_at", "members_only")
    inlines = [EquipmentInline, ParticipantInline]
    actions = ["cancel_selected", "flag_hide_reviews", "clear_flag"]

    @admin.action(description="Suspicious trip: hide all its reviews and block new ones")
    def flag_hide_reviews(self, request, queryset):
        hidden = sum(review_services.flag_trip_hide_reviews(t, request.user) for t in queryset)
        self.message_user(request, f"Flagged {queryset.count()} trip(s); hid {hidden} review(s).",
                          messages.SUCCESS)

    @admin.action(description="Checked and OK: clear the flag and restore its reviews")
    def clear_flag(self, request, queryset):
        restored = sum(review_services.clear_trip_flag(t, request.user) for t in queryset)
        self.message_user(request, f"Cleared {queryset.count()} trip(s); restored {restored} "
                                   f"review(s).", messages.SUCCESS)

    @admin.action(description="Cancel selected trips (participants are notified)")
    def cancel_selected(self, request, queryset):
        done = 0
        for trip in queryset:
            try:
                services.cancel_trip(trip, request.user)
                done += 1
            except ValidationError as exc:
                self.message_user(request, f"{trip}: {exc.detail}", messages.ERROR)
        if done:
            self.message_user(request, f"Cancelled {done} trip(s).", messages.SUCCESS)


@admin.register(AttendanceAppeal)
class AttendanceAppealAdmin(AnnotatedOrderingMixin, admin.ModelAdmin):
    """No-show appeals. Open ones come first. Decide with the actions, not by editing."""

    list_display = ("trip", "person", "status", "checked_in", "reason", "created_at", "decided_by")
    list_filter = ("status",)
    search_fields = ("participant__trip__title", "reason")
    readonly_fields = ("trip", "person", "checked_in", "marked_by", "reason", "status",
                       "decided_by", "decided_at", "decision_note", "created_at")
    fields = readonly_fields
    list_select_related = ("participant__trip", "participant__user", "decided_by")
    actions = ["approve_selected", "reject_selected"]

    def annotate_queryset(self, queryset):
        return queryset.annotate(_waiting=Case(
            When(status=AppealStatus.OPEN, then=Value(1)), default=Value(0),
            output_field=IntegerField()))

    def get_ordering(self, request):
        return ("-_waiting", "-created_at")

    @admin.display(description="Trip")
    def trip(self, obj):
        return obj.participant.trip

    @admin.display(description="Person")
    def person(self, obj):
        return obj.participant.user

    @admin.display(description="Checked in", boolean=True)
    def checked_in(self, obj):
        return obj.participant.checked_in_at is not None

    @admin.display(description="Attendance marked by")
    def marked_by(self, obj):
        return obj.participant.attendance_marked_by

    def has_add_permission(self, request):
        return False  # appeals come only from the participant, through the app

    def has_delete_permission(self, request, obj=None):
        return False  # the record of a decision stays

    @admin.action(description="Approve: mark as attended (they can then review)")
    def approve_selected(self, request, queryset):
        _run(self, request, queryset, lambda a: services.decide_appeal(a, request.user, approve=True),
             "Approved {n} appeal(s).")

    @admin.action(description="Reject (with a reason shown to the participant)")
    def reject_selected(self, request, queryset):
        return _reject_with_note(
            self, request, queryset,
            lambda a, note: services.decide_appeal(a, request.user, approve=False, note=note),
            "Reject appeal",
            intro="The following appeal(s) will be rejected and the person stays a no-show. The "
                  "reason is shown to them. An appeal cannot be sent twice.",
        )


@admin.register(EmergencyContactAccess)
class EmergencyContactAccessAdmin(admin.ModelAdmin):
    """Audit log only: who opened whose shared contact, and when. Never shows the contact."""

    list_display = ("accessed_at", "trip", "organizer", "participant")
    list_filter = ("accessed_at",)
    search_fields = ("trip__title",)
    readonly_fields = ("trip", "organizer", "participant", "accessed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # an audit log must not be editable
