import django_filters
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from . import services
from .models import Answer, AnswerStatus, Question, QuestionStatus
from .serializers import (
    AcceptSerializer,
    AnswerSerializer,
    AnswerWriteSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
    QuestionWriteSerializer,
)


class QuestionPagination(PageNumberPagination):
    page_size = 20


class QuestionFilter(django_filters.FilterSet):
    location = django_filters.NumberFilter(field_name="location_id",
                                           help_text="Campsite id")
    status = django_filters.MultipleChoiceFilter(choices=QuestionStatus.choices)
    unanswered = django_filters.BooleanFilter(method="filter_unanswered")

    class Meta:
        model = Question
        fields = ["location", "status", "unanswered"]

    def filter_unanswered(self, qs, name, value):
        if value is None:
            return qs
        return qs.filter(answer_count=0) if value else qs.filter(answer_count__gt=0)


@extend_schema(tags=["q&a"])
class QuestionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, mixins.UpdateModelMixin,
                      viewsets.GenericViewSet):
    """
    Q&A forum. Reading is public; posting needs an account.
    list ?location=<campsite id> shows the questions about one campsite.
    """

    pagination_class = QuestionPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = QuestionFilter
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "answer_count"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Question.objects.select_related("author__profile", "location", "last_edited_by__profile") \
            .annotate(answer_count=Count("answers", filter=Q(answers__status=AnswerStatus.PUBLISHED)))
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        return qs.exclude(status=QuestionStatus.HIDDEN)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action in ("hide", "restore"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        return {
            "list": QuestionListSerializer,
            "create": QuestionWriteSerializer,
            "partial_update": QuestionWriteSerializer,
            "update": QuestionWriteSerializer,
            "answers": AnswerWriteSerializer,
            "accept": AcceptSerializer,
        }.get(self.action, QuestionDetailSerializer)

    def _detail(self, question, code=status.HTTP_200_OK):
        question = self.get_queryset().get(pk=question.pk)
        return Response(QuestionDetailSerializer(question, context={"request": self.request}).data,
                        status=code)

    @extend_schema(responses={201: QuestionDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = QuestionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._detail(serializer.save(author=request.user), status.HTTP_201_CREATED)

    @extend_schema(responses=QuestionDetailSerializer)
    def update(self, request, *args, **kwargs):
        question = self.get_object()
        serializer = QuestionWriteSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = {k: v for k, v in serializer.validated_data.items() if k in ("title", "body")}
        return self._detail(services.edit_question(question, request.user, data))

    @extend_schema(request=AnswerWriteSerializer, responses={201: AnswerSerializer})
    @action(detail=True, methods=["post"])
    def answers(self, request, pk=None):
        """Post an answer."""
        serializer = AnswerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = services.post_answer(self.get_object(), request.user,
                                      serializer.validated_data["body"])
        return Response(AnswerSerializer(answer).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=AcceptSerializer, responses=QuestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """The asker marks the most helpful answer (question becomes 'answered')."""
        serializer = AcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = services.accept_answer(self.get_object(), request.user,
                                          serializer.validated_data["answer"])
        return self._detail(question)

    @extend_schema(request=None, responses=QuestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._detail(services.close_question(self.get_object(), request.user))

    @extend_schema(request=None, responses=QuestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        return self._detail(services.set_question_hidden(self.get_object(), True))

    @extend_schema(request=None, responses=QuestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        return self._detail(services.set_question_hidden(self.get_object(), False))


@extend_schema(tags=["q&a"])
class AnswerViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Edit your own answer; moderators hide / restore answers."""

    http_method_names = ["patch", "post", "head", "options"]
    serializer_class = AnswerWriteSerializer

    def get_queryset(self):
        return Answer.objects.select_related("question", "author__profile") \
            .exclude(question__status=QuestionStatus.HIDDEN)

    def get_permissions(self):
        if self.action in ("hide", "restore"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @extend_schema(request=AnswerWriteSerializer, responses=AnswerSerializer)
    def partial_update(self, request, *args, **kwargs):
        serializer = AnswerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answer = services.edit_answer(self.get_object(), request.user,
                                      serializer.validated_data["body"])
        return Response(AnswerSerializer(answer).data)

    @extend_schema(request=None, responses=AnswerSerializer)
    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        return Response(AnswerSerializer(services.set_answer_hidden(self.get_object(), True)).data)

    @extend_schema(request=None, responses=AnswerSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        return Response(AnswerSerializer(services.set_answer_hidden(self.get_object(), False)).data)
