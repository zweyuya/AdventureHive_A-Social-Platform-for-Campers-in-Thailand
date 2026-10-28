from django.contrib import admin, messages
from rest_framework.exceptions import ValidationError

from reviews import services as review_services

from . import services
from .models import EmergencyContactAccess, Trip, TripEquipmentItem, TripParticipant


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
