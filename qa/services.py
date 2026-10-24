"""
Q&A forum workflow ("Ask about this campsite").

Question:  open ──asker accepts an answer──▶ answered ──asker/moderator──▶ closed
             ▲                                   │
             └── accepted answer hidden ◀────────┘          any ──moderator──▶ hidden
Answer:    published ──moderator──▶ hidden

Post-moderated: content appears immediately; moderators hide what breaks the
rules. Versioning: current version + edited_at (and last_edited_by on questions).
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from notifications.models import NotificationType, ReferenceType
from notifications.services import notify

from .models import Answer, AnswerStatus, Question, QuestionStatus

ANSWERABLE = (QuestionStatus.OPEN, QuestionStatus.ANSWERED)


class QAError(ValidationError):
    """A Q&A rule was broken (HTTP 400)."""


def _lock(question: Question) -> Question:
    return Question.objects.select_for_update().get(pk=question.pk)


@transaction.atomic
def edit_question(question: Question, user, data: dict) -> Question:
    question = _lock(question)
    if question.author_id != user.pk:
        raise PermissionDenied("Only the author can edit this question.")
    if question.status not in ANSWERABLE:
        raise QAError(f"A {question.status} question cannot be edited.")
    for field in ("title", "body"):
        if field in data:
            setattr(question, field, data[field])
    question.edited_at = timezone.now()
    question.last_edited_by = user
    question.save()
    return question


@transaction.atomic
def post_answer(question: Question, user, body: str) -> Answer:
    question = _lock(question)
    if question.status not in ANSWERABLE:
        raise QAError(f"This question is {question.status} and no longer accepts answers.")
    answer = Answer.objects.create(question=question, author=user, body=body)
    if question.author_id != user.pk:
        notify(question.author, NotificationType.ANSWER_POSTED, ReferenceType.QUESTION,
               question.pk, actor=user)
    return answer


@transaction.atomic
def edit_answer(answer: Answer, user, body: str) -> Answer:
    answer = Answer.objects.select_for_update().get(pk=answer.pk)
    if answer.author_id != user.pk:
        raise PermissionDenied("Only the author can edit this answer.")
    if answer.status == AnswerStatus.HIDDEN:
        raise QAError("A hidden answer cannot be edited.")
    answer.body = body
    answer.edited_at = timezone.now()
    answer.save()
    return answer


@transaction.atomic
def accept_answer(question: Question, user, answer: Answer) -> Question:
    question = _lock(question)
    if question.author_id != user.pk:
        raise PermissionDenied("Only the person who asked can accept an answer.")
    if question.status not in ANSWERABLE:
        raise QAError(f"A {question.status} question cannot accept answers.")
    if answer.question_id != question.pk or answer.status != AnswerStatus.PUBLISHED:
        raise QAError({"answer_id": "Choose a visible answer to this question."})
    question.accepted_answer = answer
    question.status = QuestionStatus.ANSWERED
    question.save(update_fields=["accepted_answer", "status"])
    return question


@transaction.atomic
def close_question(question: Question, user) -> Question:
    question = _lock(question)
    if question.author_id != user.pk and not user.is_staff:
        raise PermissionDenied("Only the asker or a moderator can close this question.")
    if question.status not in ANSWERABLE:
        raise QAError(f"A {question.status} question cannot be closed.")
    question.status = QuestionStatus.CLOSED
    question.save(update_fields=["status"])
    return question


@transaction.atomic
def set_question_hidden(question: Question, hidden: bool) -> Question:
    question = _lock(question)
    if hidden:
        question.status = QuestionStatus.HIDDEN
    elif question.status == QuestionStatus.HIDDEN:
        question.status = (QuestionStatus.ANSWERED if question.accepted_answer_id
                           else QuestionStatus.OPEN)
    question.save(update_fields=["status"])
    return question


@transaction.atomic
def set_answer_hidden(answer: Answer, hidden: bool) -> Answer:
    answer = Answer.objects.select_for_update().get(pk=answer.pk)
    answer.status = AnswerStatus.HIDDEN if hidden else AnswerStatus.PUBLISHED
    answer.save(update_fields=["status"])
    if hidden:
        # A hidden answer can't stay "accepted": the question re-opens.
        question = Question.objects.select_for_update().get(pk=answer.question_id)
        if question.accepted_answer_id == answer.pk:
            question.accepted_answer = None
            if question.status == QuestionStatus.ANSWERED:
                question.status = QuestionStatus.OPEN
            question.save(update_fields=["accepted_answer", "status"])
    return answer
