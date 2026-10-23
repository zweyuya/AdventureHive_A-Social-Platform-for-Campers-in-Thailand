from django.contrib import admin

from .models import CampingGroup, GroupMember


class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0
    raw_id_fields = ("user",)


@admin.register(CampingGroup)
class CampingGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "privacy_type", "member_count", "created_at")
    list_filter = ("category", "privacy_type")
    search_fields = ("name",)
    readonly_fields = ("member_count",)
    inlines = [GroupMemberInline]
