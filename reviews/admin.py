from django.contrib import admin, messages

from . import services
from .models import Review, ReviewStatus


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Reviews are written only by verified attendees; moderators can hide / restore them."""

    list_display = ("location", "user", "trip", "rating", "status", "created_at", "edited_at")
    list_filter = ("status", "rating")
    search_fields = ("location__name", "review_text")
    readonly_fields = ("location", "trip", "user", "rating", "review_text", "status",
                       "created_at", "edited_at")
    actions = ["hide_selected", "restore_selected"]

    def has_add_permission(self, request):
        return False  # reviews come only from attended participants via the app

    @admin.action(description="Hide selected reviews (removed from ratings)")
    def hide_selected(self, request, queryset):
        for review in queryset:
            services.set_review_status(review, ReviewStatus.HIDDEN)
        self.message_user(request, f"Hid {queryset.count()} review(s).", messages.SUCCESS)

    @admin.action(description="Restore selected reviews")
    def restore_selected(self, request, queryset):
        for review in queryset:
            services.set_review_status(review, ReviewStatus.PUBLISHED)
        self.message_user(request, f"Restored {queryset.count()} review(s).", messages.SUCCESS)
