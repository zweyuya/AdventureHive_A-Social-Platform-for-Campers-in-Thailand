from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserChangeAdminForm, UserCreationAdminForm
from .models import EmergencyContact, InterestTag, Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    filter_horizontal = ("interest_tags",)


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
