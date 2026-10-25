from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.fields import EncryptedTextField
from core.models import ExperienceLevel


class UserStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    SUSPENDED = "suspended", "Suspended"
    BANNED = "banned", "Banned"
    DELETED = "deleted", "Deleted"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        # Admin accounts created from the CLI count as having consented.
        extra.setdefault("pdpa_consent_at", timezone.now())
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Schema table `users`. Logs in with email.
    Django's `password` field replaces `password_hash`; `is_staff` is Django's
    platform-admin flag (the schema deliberately leaves platform roles to Django).
    """

    email = models.EmailField(max_length=255, unique=True)
    # NULL (not "") when absent, so the unique constraint allows many users without a phone.
    phone = models.CharField(max_length=30, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=UserStatus.choices, default=UserStatus.ACTIVE)
    pdpa_consent_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"
        constraints = [
            # A deleted account must be marked deleted, and vice versa.
            models.CheckConstraint(
                name="users_deleted_status_consistent",
                condition=(Q(deleted_at__isnull=True) & ~Q(status=UserStatus.DELETED))
                | (Q(deleted_at__isnull=False) & Q(status=UserStatus.DELETED)),
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        """Used by Django and SimpleJWT to block login for non-active accounts."""
        return self.status == UserStatus.ACTIVE and self.deleted_at is None

    def save(self, *args, **kwargs):
        if self.phone == "":
            self.phone = None
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)


class InterestTag(models.Model):
    tag_name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "interest_tags"
        ordering = ["tag_name"]

    def __str__(self):
        return self.tag_name


class Profile(models.Model):
    """Schema table `profiles` — one per user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=100, blank=True)
    camping_experience_level = models.CharField(
        max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.BEGINNER
    )
    # 400×400 JPEG produced by accounts.images.process_avatar (metadata stripped)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    interest_tags = models.ManyToManyField(
        InterestTag, blank=True, related_name="profiles", db_table="profile_interest_tags"
    )

    class Meta:
        db_table = "profiles"

    def __str__(self):
        return self.display_name


class EmergencyContact(models.Model):
    """
    Schema table `emergency_contacts`.
    One contact per user (matches the singular /emergency-contact/ endpoint).
    name and phone are encrypted at rest; readable only by the owner via the API.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="emergency_contact")
    name = EncryptedTextField()
    phone = EncryptedTextField()
    relationship = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emergency_contacts"

    def __str__(self):
        return f"Emergency contact of user {self.user_id}"
