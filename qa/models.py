"""
Q&A forum ("Ask about this campsite"). Required by the content-management
problem set. Versioning: current version + edited_at / last_edited_by.
Moderation: post-moderated; moderators set status = hidden.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class QuestionStatus(models.TextChoices):
    OPEN = "open", "Open"
    ANSWERED = "answered", "Answered"  # has an accepted answer
    CLOSED = "closed", "Closed"
    HIDDEN = "hidden", "Hidden"


class AnswerStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"


class Question(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions"
    )
    location = models.ForeignKey(  # NULL = general camping question
        "locations.Location", null=True, blank=True,
        on_delete=models.CASCADE, related_name="questions",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(
        max_length=10, choices=QuestionStatus.choices, default=QuestionStatus.OPEN
    )
    accepted_answer = models.OneToOneField(
        "qa.Answer", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        db_table = "questions"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["location", "status"])]
        constraints = [
            models.CheckConstraint(
                name="questions_answered_has_accepted",
                condition=~Q(status=QuestionStatus.ANSWERED) | Q(accepted_answer__isnull=False),
            ),
        ]

    def __str__(self):
        return self.title


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="answers"
    )
    body = models.TextField()
    status = models.CharField(
        max_length=10, choices=AnswerStatus.choices, default=AnswerStatus.PUBLISHED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "answers"
        ordering = ["created_at"]

    def __str__(self):
        return f"Answer to '{self.question}' by {self.author}"
