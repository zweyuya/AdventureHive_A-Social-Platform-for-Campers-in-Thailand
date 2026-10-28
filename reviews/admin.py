from django.contrib import admin, messages
from django.db.models import Count, Q

from . import services
from .models import ReportStatus, Review, ReviewReport, ReviewStatus


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Reviews are written only by verified attendees; moderators can hide / restore them."""

    list_display = ("location", "user", "trip", "rating", "status", "hidden_reason",
                    "open_reports", "created_at", "edited_at")
    list_filter = ("status", "hidden_reason", "rating")
    search_fields = ("location__name", "review_text")
    readonly_fields = ("location", "trip", "user", "rating", "review_text", "status",
                       "hidden_reason", "created_at", "edited_at")
    actions = ["hide_selected", "restore_selected"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _open_reports=Count("reports", filter=Q(reports__status=ReportStatus.OPEN)))

    @admin.display(description="Open reports", ordering="_open_reports")
    def open_reports(self, obj):
        return obj._open_reports

    def has_add_permission(self, request):
        return False  # reviews come only from attended participants via the app

    @admin.action(description="Hide selected reviews (removed from ratings, reports closed)")
    def hide_selected(self, request, queryset):
        for review in queryset:
            services.resolve_reports(review, request.user, hide=True)
        self.message_user(request, f"Hid {queryset.count()} review(s).", messages.SUCCESS)

    @admin.action(description="Restore selected reviews")
    def restore_selected(self, request, queryset):
        for review in queryset:
            services.set_review_status(review, ReviewStatus.PUBLISHED)
        self.message_user(request, f"Restored {queryset.count()} review(s).", messages.SUCCESS)


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    """Moderation queue: members' reports on reviews."""

    list_display = ("review", "reason", "reporter", "status", "created_at", "resolved_by")
    list_filter = ("status", "reason")
    search_fields = ("review__review_text", "details")
    readonly_fields = ("review", "reporter", "reason", "details", "status", "resolved_by",
                       "resolved_at", "created_at")
    actions = ["hide_reviews", "dismiss"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Hide the reported review(s) and close their reports")
    def hide_reviews(self, request, queryset):
        reviews = {r.review for r in queryset.select_related("review")}
        for review in reviews:
            services.resolve_reports(review, request.user, hide=True)
        self.message_user(request, f"Hid {len(reviews)} review(s).", messages.SUCCESS)

    @admin.action(description="Dismiss: keep the review(s), close their reports")
    def dismiss(self, request, queryset):
        reviews = {r.review for r in queryset.select_related("review")}
        for review in reviews:
            services.resolve_reports(review, request.user, hide=False)
        self.message_user(request, f"Dismissed reports on {len(reviews)} review(s).",
                          messages.SUCCESS)
