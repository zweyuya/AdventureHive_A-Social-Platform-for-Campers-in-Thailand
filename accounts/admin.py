from django.contrib import admin, messages
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserChangeAdminForm, UserCreationAdminForm
from .models import EmergencyContact, InterestTag, Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    filter_horizontal = ("interest_tags",)
    # Photos are uploaded by the user through the app (which strips GPS metadata);
    # moderators can only view or remove them.
    exclude = ("avatar",)
    readonly_fields = ("photo",)

    @admin.display(description="Profile photo")
    def photo(self, obj):
        if not obj.avatar:
            return "No photo"
        return format_html('<img src="{}" style="width:96px;height:96px;border-radius:50%">', obj.avatar.url)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm
    ordering = ("-created_at",)
    list_display = ("email", "status", "is_staff", "created_at")
    list_filter = ("status", "is_staff", "is_superuser")
    search_fields = ("email",)
    readonly_fields = ("created_at", "last_login", "pdpa_consent_at")
    inlines = [ProfileInline]
    actions = ["remove_profile_photos"]

    @admin.action(description="Remove profile photo (moderation)")
    def remove_profile_photos(self, request, queryset):
        removed = 0
        for user in queryset.select_related("profile"):
            if user.profile.avatar:
                user.profile.avatar.delete(save=True)
                removed += 1
        self.message_user(request, f"Removed {removed} profile photo(s).", messages.SUCCESS)
    fieldsets = (
        (None, {"fields": ("email", "password", "phone")}),
        ("Status", {"fields": ("status", "deleted_at", "pdpa_consent_at")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "usable_password", "password1", "password2")}),
    )


@admin.register(InterestTag)
class InterestTagAdmin(admin.ModelAdmin):
    search_fields = ("tag_name",)


# Emergency contacts are deliberately NOT registered in the admin:
# no role, including admin, may read another user's emergency contact.
_ = EmergencyContact
