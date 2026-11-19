from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from rest_framework.exceptions import ValidationError

from .forms import UserChangeAdminForm, UserCreationAdminForm
from .models import EmergencyContact, InterestTag, Profile, User, UserStatus
from .services import delete_account


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
    list_display = ("email", "status", "is_moderator", "is_staff", "created_at")
    list_filter = ("status", "is_moderator", "is_staff", "is_superuser")
    search_fields = ("email",)
    readonly_fields = ("created_at", "last_login", "pdpa_consent_at")
    inlines = [ProfileInline]

    def get_inlines(self, request, obj):
        # A new user's profile is created by the post_save signal; showing the inline on
        # the "Add user" page would try to create a second one (unique user_id error).
        return self.inlines if obj else []
    actions = ["remove_profile_photos", "make_moderators", "remove_moderators", "delete_accounts"]

    @admin.action(description="Make campsite moderator (reviews submissions in the app only)")
    def make_moderators(self, request, queryset):
        done = queryset.filter(status=UserStatus.ACTIVE).update(is_moderator=True)
        self.message_user(request, f"{done} user(s) can now moderate campsites.", messages.SUCCESS)

    @admin.action(description="Remove campsite moderator role")
    def remove_moderators(self, request, queryset):
        done = queryset.update(is_moderator=False)
        self.message_user(request, f"Removed the role from {done} user(s).", messages.SUCCESS)

    def has_delete_permission(self, request, obj=None):
        """No hard delete: the cascade removes RSVP rows without updating the seat count or
        promoting the waitlist. Accounts are removed with the "Delete account" action."""
        return False

    @admin.action(description="Delete account (erase personal data, free seats)")
    def delete_accounts(self, request, queryset):
        users = queryset.exclude(status=UserStatus.DELETED).exclude(pk=request.user.pk)
        if "apply" not in request.POST:
            return TemplateResponse(request, "admin/accounts/delete_account_confirmation.html", {
                **self.admin_site.each_context(request),
                "title": "Delete account",
                "objects": users,
                "action": request.POST.get("action"),
                "opts": self.model._meta,
                "selected": request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME),
            })
        done = 0
        for user in users:
            try:
                delete_account(user)
                done += 1
            except ValidationError as exc:
                self.message_user(request, f"{user}: {exc.detail}", messages.ERROR)
        if done:
            self.message_user(request, f"Deleted {done} account(s).", messages.SUCCESS)

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
        ("Permissions", {"fields": ("is_moderator", "is_staff", "is_superuser", "groups",
                                    "user_permissions")}),
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
