from django.contrib import admin, messages
from rest_framework.exceptions import ValidationError

from . import services
from .models import Trip, TripEquipmentItem, TripParticipant


class EquipmentInline(admin.TabularInline):
    model = TripEquipmentItem
    extra = 0


class ParticipantInline(admin.TabularInline):
    """Read-only: seats and the waitlist must change only through the RSVP rules."""

    model = TripParticipant
    fk_name = "trip"
    extra = 0
    can_delete = False
    fields = ("user", "status", "waitlist_position", "joined_at",
              "attendance_marked_by", "attendance_marked_at")
    readonly_fields = fields
    ordering = ("status", "waitlist_position", "joined_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "organizer", "status", "start_datetime",
                    "confirmed_count", "participant_capacity")
    list_filter = ("status", "difficulty")
    search_fields = ("title", "location__name")
    raw_id_fields = ("organizer", "location", "group")
    readonly_fields = ("status", "confirmed_count", "created_at", "updated_at")
    inlines = [EquipmentInline, ParticipantInline]
    actions = ["cancel_selected"]

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
