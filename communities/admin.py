from django.contrib import admin

from .models import CampingGroup, GroupMember


class GroupMemberInline(admin.TabularInline):
    """Read-only: membership changes go through the app so member_count stays correct."""

    model = GroupMember
    extra = 0
    can_delete = False
    fields = ("user", "role_in_group", "status", "joined_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CampingGroup)
class CampingGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "privacy_type", "member_count", "created_by", "created_at")
    list_filter = ("category", "privacy_type")
    search_fields = ("name",)
    readonly_fields = ("member_count", "created_by", "created_at")
    inlines = [GroupMemberInline]
