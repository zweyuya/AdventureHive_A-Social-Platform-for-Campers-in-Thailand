from rest_framework import serializers

from core.people import person as _person

from locations.models import Location

from .models import Answer, AnswerStatus, Question


class AnswerSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ["id", "question", "body", "author", "is_accepted", "status",
                  "created_at", "edited_at"]
        read_only_fields = fields

    def get_author(self, obj) -> dict:
        return _person(obj.author)

    def get_is_accepted(self, obj) -> bool:
        return obj.question.accepted_answer_id == obj.pk


class AnswerWriteSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)


class QuestionListSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    campsite = serializers.SerializerMethodField()
    answer_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Question
        fields = ["id", "title", "status", "campsite", "author", "answer_count",
                  "accepted_answer", "created_at", "edited_at"]

    def get_author(self, obj) -> dict:
        return _person(obj.author)

    def get_campsite(self, obj) -> dict | None:
        if obj.location_id is None:
            return None
        return {"id": obj.location_id, "name": obj.location.name}


class QuestionDetailSerializer(QuestionListSerializer):
    answers = serializers.SerializerMethodField()
    last_edited_by = serializers.SerializerMethodField()

    class Meta(QuestionListSerializer.Meta):
        fields = QuestionListSerializer.Meta.fields + ["body", "answers", "last_edited_by"]

    def get_answers(self, obj) -> list:
        user = self.context["request"].user
        qs = obj.answers.select_related("author__profile", "question").order_by("created_at")
        if not (user.is_authenticated and user.is_staff):
            qs = qs.filter(status=AnswerStatus.PUBLISHED)
        return AnswerSerializer(qs, many=True).data

    def get_last_edited_by(self, obj) -> dict | None:
        return _person(obj.last_edited_by) if obj.last_edited_by_id else None


class QuestionWriteSerializer(serializers.ModelSerializer):
    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.published(), source="location",
        required=False, allow_null=True,
        help_text="Published campsite this question is about (optional).",
    )

    class Meta:
        model = Question
        fields = ["location_id", "title", "body"]


class AcceptSerializer(serializers.Serializer):
    answer_id = serializers.PrimaryKeyRelatedField(queryset=Answer.objects.all(), source="answer")
