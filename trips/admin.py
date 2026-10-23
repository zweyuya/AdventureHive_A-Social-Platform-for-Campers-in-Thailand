from django.contrib import admin

from .models import Trip, TripEquipmentItem, TripParticipant


class EquipmentInline(admin.TabularInline):
    model = TripEquipmentItem
    extra = 0


class ParticipantInline(admin.TabularInline):
    model = TripParticipant
    fk_name = "trip"
    extra = 0
    raw_id_fields = ("user", "attendance_marked_by")
    readonly_fields = ("joined_at",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "title", "location", "organizer", "status", "start_datetime",
        "confirmed_count", "participant_capacity",
    )
    list_filter = ("status", "difficulty")
    search_fields = ("title",)
    raw_id_fields = ("organizer", "location", "group")
    readonly_fields = ("confirmed_count", "created_at", "updated_at")
    inlines = [EquipmentInline, ParticipantInline]
