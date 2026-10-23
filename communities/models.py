"""
Camping groups. The app is called `communities` and the model `CampingGroup`
because `groups` clashes with Django's auth Group / User.groups.
"""
from django.conf import settings
from django.db import models


class GroupCategory(models.TextChoices):
    CAR_CAMPING = "car_camping", "Car camping"
    BACKPACKING = "backpacking", "Backpacking"
    FAMILY_CAMPING = "family_camping", "Family camping"
    VAN_LIFE = "van_life", "Van life"
    GENERAL = "general", "General"


class PrivacyType(models.TextChoices):
    PUBLIC = "public", "Public"
    PRIVATE = "private", "Private"


class GroupMemberRole(models.TextChoices):
    MEMBER = "member", "Member"
    CO_ADMIN = "co_admin", "Co-admin"
    ADMIN = "admin", "Admin"


class GroupMemberStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"  # left the group
    REMOVED = "removed", "Removed"
    BANNED = "banned", "Banned"


class CampingGroup(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=GroupCategory.choices, default=GroupCategory.GENERAL
    )
    privacy_type = models.CharField(
        max_length=10, choices=PrivacyType.choices, default=PrivacyType.PUBLIC
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_groups"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    member_count = models.PositiveIntegerField(default=0)  # active members only

    class Meta:
        db_table = "groups"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    """
    Surrogate id + unique (group, user) instead of a composite PK
    (works cleanly with DRF and the admin).
    """

    group = models.ForeignKey(CampingGroup, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships"
    )
    role_in_group = models.CharField(
        max_length=10, choices=GroupMemberRole.choices, default=GroupMemberRole.MEMBER
    )
    status = models.CharField(
        max_length=10, choices=GroupMemberStatus.choices, default=GroupMemberStatus.ACTIVE
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "group_members"
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="group_members_unique"),
        ]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.user} in {self.group} ({self.role_in_group})"

    @property
    def is_active_admin(self):
        return self.status == GroupMemberStatus.ACTIVE and self.role_in_group == GroupMemberRole.ADMIN

