from django.db import models


class TimeStampedModel(models.Model):
    """created_at / updated_at on every table that changes over time."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ExperienceLevel(models.TextChoices):
    """Shared by profiles (camping_experience_level) and trips (min_experience_level)."""

    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"
    EXPERT = "expert", "Expert"

    @classmethod
    def rank(cls, value: str) -> int:
        """Numeric order so levels can be compared: rank(user) >= rank(trip)."""
        return [c.value for c in cls].index(value)
