from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.template.response import TemplateResponse
from rest_framework.exceptions import ValidationError

from core.provinces import canonical_province, check_pin

from . import services
from .models import Authority, Location, LocationRevision, LocationStatus, RevisionStatus


class RejectForm(forms.Form):
    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "cols": 70}),
        label="Reason (shown to the submitter)",
    )


def _error_text(exc: ValidationError) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return "; ".join(f"{k}: {v}" for k, v in detail.items())
    if isinstance(detail, list):
        return " ".join(str(d) for d in detail)
    return str(detail)


def _run(modeladmin, request, queryset, fn, success_msg):
    done = 0
    for obj in queryset:
        try:
            fn(obj)
            done += 1
        except ValidationError as exc:
            modeladmin.message_user(request, f"{obj}: {_error_text(exc)}", messages.ERROR)
    if done:
        modeladmin.message_user(request, success_msg.format(n=done), messages.SUCCESS)


def _reject_with_note(modeladmin, request, queryset, fn, title):
    """Intermediate page: ask for the rejection reason, then reject."""
    if "apply" in request.POST:
        form = RejectForm(request.POST)
        if form.is_valid():
            note = form.cleaned_data["note"]
            _run(modeladmin, request, queryset, lambda o: fn(o, note), "Rejected {n} item(s).")
            return None
    else:
        form = RejectForm()
    return TemplateResponse(request, "admin/locations/reject_confirmation.html", {
        **modeladmin.admin_site.each_context(request),
        "title": title,
        "objects": queryset,
        "form": form,
        "action": request.POST.get("action"),
        "opts": modeladmin.model._meta,
        "selected": request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME),
    })


@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "authority_type", "phone")
    list_filter = ("authority_type",)
    search_fields = ("name",)


class LocationRevisionInline(admin.TabularInline):
    model = LocationRevision
    fk_name = "location"
    extra = 0
    fields = ("version_no", "status", "edited_by", "edit_summary", "reviewed_by", "created_at")
    readonly_fields = fields
    can_delete = False
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


class LocationAdminForm(forms.ModelForm):
    """Moderator edits follow the same pin rule as the API (inside Thailand, province matches)."""

    class Meta:
        model = Location
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if self.instance.pk and not any(f in self.changed_data for f in services.PIN_FIELDS):
            return data
        values = {f: data.get(f) for f in services.PIN_FIELDS}
        try:
            data["province"] = services.check_pin_and_province(values)["province"]
        except ValidationError as exc:
            for field, msg in exc.detail.items():
                self.add_error(field, " ".join(str(m) for m in msg) if isinstance(msg, list) else str(msg))
        return data


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    form = LocationAdminForm
    list_display = ("name", "province", "pin_ok", "category", "status", "has_photo", "created_by",
                    "permit_status", "current_version", "updated_at")
    list_filter = ("status", "province", "category", "permit_status")
    search_fields = ("name", "province")
    readonly_fields = ("avg_rating", "review_count", "current_version", "reviewed_by",
                       "reviewed_at", "created_by", "created_at", "updated_at", "photo_preview",
                       "map_check")
    raw_id_fields = ("authority",)
    inlines = [LocationRevisionInline]
    actions = ["approve_selected", "reject_selected"]
    fieldsets = (
        ("Workflow", {"fields": ("status", "moderation_note", "created_by", "reviewed_by",
                                 "reviewed_at", "current_version")}),
        ("Campsite", {"fields": ("name", "province", "category", "description",
                                 "latitude", "longitude", "map_check", "terrain_type",
                                 "elevation_m", "site_capacity")}),
        ("Photo", {"fields": ("cover_image", "photo_preview", "cover_image_credit"),
                   "description": "Use your own photos, or openly licensed ones (e.g. Wikimedia "
                                  "Commons) and fill in the credit."}),
        ("Facilities", {"fields": ("has_water_source", "has_restrooms", "fire_pit_allowed")}),
        ("Permits & rules", {"fields": ("authority", "permit_status", "permit_details",
                                        "permit_booking_url", "rules", "permit_info_source",
                                        "permit_info_verified_at")}),
        ("Ratings", {"fields": ("avg_rating", "review_count", "created_at", "updated_at")}),
    )

    @admin.display(description="Preview")
    def photo_preview(self, obj):
        if not obj.cover_image:
            return "No photo yet — the app shows an illustration."
        return format_html('<img src="{}" style="max-width:360px;border-radius:8px">', obj.cover_image.url)

    @admin.display(boolean=True, description="Photo")
    def has_photo(self, obj):
        return bool(obj.cover_image)

    @admin.display(boolean=True, description="Pin OK")
    def pin_ok(self, obj):
        """Pin inside Thailand and in the stated province."""
        return canonical_province(obj.province) in check_pin(obj.latitude, obj.longitude).allowed

    @admin.display(description="Map check")
    def map_check(self, obj):
        if obj.pk is None:
            return "Shown after the campsite is saved."
        lat, lng = obj.latitude, obj.longitude
        pin = check_pin(lat, lng)
        if not pin.in_thailand:
            where = pin.country or "outside Thailand"
            verdict = format_html('<b style="color:#b91c1c">✗ The pin is in {} — not in Thailand.</b>',
                                  where)
        elif canonical_province(obj.province) in pin.allowed:
            verdict = format_html('<b style="color:#15803d">✓ The pin is in {}.</b>', pin.province)
        else:
            verdict = format_html('<b style="color:#b45309">⚠ The pin is in {}, but the province '
                                  'says {}.</b>', pin.province, obj.province)

        near = services.nearby_campsites(lat, lng, exclude_id=obj.pk)
        if near:
            items = format_html_join("", '<li><a href="{}">{}</a> ({}) — {} km</li>', (
                (reverse("admin:locations_location_change", args=[loc.pk]), loc.name,
                 loc.get_status_display(), f"{d:.2f}") for loc, d in near))
            nearby = format_html('<p style="color:#b45309"><b>⚠ Possible duplicate</b> — other '
                                 'campsites within {} km:</p><ul>{}</ul>', services.NEARBY_KM, items)
        else:
            nearby = format_html("<p>No other campsites within {} km.</p>", services.NEARBY_KM)

        d = 0.04  # degrees around the pin shown in the preview (~4 km)
        embed = (f"https://www.openstreetmap.org/export/embed.html?bbox={lng - d},{lat - d},"
                 f"{lng + d},{lat + d}&layer=mapnik&marker={lat},{lng}")
        link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=13/{lat}/{lng}"
        return format_html(
            '{}{}<iframe src="{}" style="width:480px;max-width:100%;height:300px;border:1px solid '
            '#ccc;border-radius:8px"></iframe><br><a href="{}" target="_blank" rel="noopener">'
            'Open in OpenStreetMap</a> · {}, {}',
            verdict, nearby, embed, link, lat, lng)

    @admin.action(description="Approve selected submissions (publish)")
    def approve_selected(self, request, queryset):
        _run(self, request, queryset.filter(status=LocationStatus.PENDING_REVIEW),
             lambda o: services.approve_submission(o, request.user), "Published {n} campsite(s).")
        skipped = queryset.exclude(status=LocationStatus.PENDING_REVIEW).count()
        if skipped:
            self.message_user(request, f"Skipped {skipped} not pending review.", messages.WARNING)

    @admin.action(description="Reject selected submissions (with reason)")
    def reject_selected(self, request, queryset):
        queryset = queryset.filter(status=LocationStatus.PENDING_REVIEW)
        if not queryset.exists():
            self.message_user(request, "Select campsites that are pending review.", messages.WARNING)
            return None
        return _reject_with_note(
            self, request, queryset,
            lambda o, note: services.reject_submission(o, request.user, note),
            "Reject campsite submissions",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            # Direct moderator edits to a published campsite still create a version.
            services.record_admin_edit(obj, request.user, form.changed_data)


@admin.register(LocationRevision)
class LocationRevisionAdmin(admin.ModelAdmin):
    list_display = ("location", "version_no", "status", "edited_by", "edit_summary", "created_at")
    list_filter = ("status",)
    search_fields = ("location__name", "edit_summary")
    readonly_fields = ("location", "version_no", "snapshot", "edit_summary", "edited_by",
                       "status", "reviewed_by", "review_note", "created_at")
    actions = ["approve_selected", "reject_selected"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Approve selected suggestions (apply as new version)")
    def approve_selected(self, request, queryset):
        _run(self, request, queryset.filter(status=RevisionStatus.PENDING),
             lambda r: services.approve_revision(r, request.user), "Applied {n} suggestion(s).")

    @admin.action(description="Reject selected suggestions (with reason)")
    def reject_selected(self, request, queryset):
        queryset = queryset.filter(status=RevisionStatus.PENDING)
        if not queryset.exists():
            self.message_user(request, "Select pending suggestions.", messages.WARNING)
            return None
        return _reject_with_note(
            self, request, queryset,
            lambda r, note: services.reject_revision(r, request.user, note),
            "Reject suggested edits",
        )
