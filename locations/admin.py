from django.contrib import admin

from .models import Authority, Location, LocationRevision


@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "authority_type", "phone")
    list_filter = ("authority_type",)
    search_fields = ("name",)


class LocationRevisionInline(admin.TabularInline):
    model = LocationRevision
    fk_name = "location"
    extra = 0
    fields = ("version_no", "status", "edited_by", "edit_summary", "created_at")
    readonly_fields = fields
    can_delete = False


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    # Approve / reject actions are added in Layer 2 (content workflow).
    list_display = ("name", "province", "category", "status", "permit_status", "current_version")
    list_filter = ("status", "province", "category", "permit_status")
    search_fields = ("name", "province")
    readonly_fields = ("avg_rating", "review_count", "current_version", "created_at", "updated_at")
    inlines = [LocationRevisionInline]


@admin.register(LocationRevision)
class LocationRevisionAdmin(admin.ModelAdmin):
    list_display = ("location", "version_no", "status", "edited_by", "created_at")
    list_filter = ("status",)
