from django.contrib import admin, messages
from django.db.models import Case, Count, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce

from core.admin_helpers import AnnotatedOrderingMixin

from . import services
from .models import ReportStatus, Review, ReviewReport, ReviewStatus


@admin.register(Review)
class ReviewAdmin(AnnotatedOrderingMixin, admin.ModelAdmin):
    """Reviews are written only by verified attendees; moderators can hide / restore them."""

    list_display = ("location", "user", "trip", "rating", "status", "hidden_reason",
                    "open_reports", "escalated", "created_at", "edited_at")
    list_filter = ("status", "hidden_reason", "rating")
    search_fields = ("location__name", "review_text")
    readonly_fields = ("location", "trip", "user", "rating", "review_text", "status",
                       "hidden_reason", "created_at", "edited_at")
    actions = ["hide_selected", "restore_selected"]

    def annotate_queryset(self, queryset):
        return queryset.annotate(
            _open_reports=Count("reports", filter=Q(reports__status=ReportStatus.OPEN)))

    def get_ordering(self, request):
        return ("-_open_reports", "-created_at")  # the most reported reviews first

    @admin.display(description="Open reports", ordering="_open_reports")
    def open_reports(self, obj):
        return obj._open_reports

    @admin.display(description="Escalated", boolean=True)
    def escalated(self, obj):
        return obj._open_reports >= services.REPORT_ESCALATION

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
class ReviewReportAdmin(AnnotatedOrderingMixin, admin.ModelAdmin):
    """Moderation queue: members' reports on reviews."""

    list_display = ("review", "escalated", "open_on_review", "reason", "reporter", "status",
                    "created_at", "resolved_by")
    list_filter = ("status", "reason")
    search_fields = ("review__review_text", "details")
    readonly_fields = ("review", "reporter", "reason", "details", "status", "resolved_by",
                       "resolved_at", "created_at")
    actions = ["hide_reviews", "dismiss"]

    def annotate_queryset(self, queryset):
        """Reviews with 3 or more open reports go to the top of the queue."""
        open_on_review = (ReviewReport.objects.filter(review=OuterRef("review"), status=ReportStatus.OPEN)
                          .order_by().values("review").annotate(n=Count("pk")).values("n"))
        return queryset.annotate(
            _open_on_review=Coalesce(Subquery(open_on_review, output_field=IntegerField()), Value(0)),
        ).annotate(_escalated=Case(
            When(status=ReportStatus.OPEN, _open_on_review__gte=services.REPORT_ESCALATION, then=Value(1)),
            default=Value(0), output_field=IntegerField()))

    def get_ordering(self, request):
        return ("-_escalated", "-_open_on_review", "-created_at")

    @admin.display(description="Escalated", boolean=True, ordering="_escalated")
    def escalated(self, obj):
        return bool(obj._escalated)

    @admin.display(description="Open reports on this review", ordering="_open_on_review")
    def open_on_review(self, obj):
        return obj._open_on_review

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
