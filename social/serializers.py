from rest_framework import serializers

from communities.models import CampingGroup
from core.people import person
from trips.models import Trip

from .models import Comment, Post, ReactionType


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()
    trip = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField(help_text="{type: count}")
    my_reaction = serializers.SerializerMethodField()
    can_moderate = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "author", "group", "trip", "content_text", "image", "status",
                  "moderation_note", "reaction_count", "reactions", "my_reaction",
                  "comment_count", "can_moderate", "is_mine", "created_at", "edited_at"]

    def _user(self):
        return self.context["request"].user

    def get_author(self, obj) -> dict:
        return person(obj.user)

    def get_group(self, obj) -> dict | None:
        return {"id": obj.group_id, "name": obj.group.name, "privacy_type": obj.group.privacy_type} \
            if obj.group_id else None

    def get_trip(self, obj) -> dict | None:
        return {"id": obj.trip_id, "title": obj.trip.title} if obj.trip_id else None

    def get_image(self, obj) -> str | None:
        return obj.image.url if obj.image else None

    def get_reactions(self, obj) -> dict:
        return self.context.get("reaction_summary", {}).get(obj.pk, {})

    def get_my_reaction(self, obj) -> str | None:
        return self.context.get("my_reactions", {}).get(obj.pk)

    def get_can_moderate(self, obj) -> bool:
        user = self._user()
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        if obj.group_id:
            return obj.group_id in self.context.get("moderated_groups", set())
        return obj.trip.organizer_id == user.pk

    def get_is_mine(self, obj) -> bool:
        return obj.user_id == getattr(self._user(), "pk", None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not (data["is_mine"] or data["can_moderate"]):
            data["moderation_note"] = ""
        return data


class PostCreateSerializer(serializers.Serializer):
    content_text = serializers.CharField(max_length=5000, allow_blank=True, required=False, default="")
    group_id = serializers.PrimaryKeyRelatedField(queryset=CampingGroup.objects.all(), source="group",
                                                  required=False, allow_null=True)
    trip_id = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all(), source="trip",
                                                 required=False, allow_null=True)
    image = serializers.FileField(required=False, allow_null=True,
                                  help_text="Optional photo: JPEG, PNG or WebP, max 5 MB.")


class PostEditSerializer(serializers.Serializer):
    content_text = serializers.CharField(max_length=5000)


class RejectPostSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=1000, help_text="Shown to the author.")


class ReactSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ReactionType.choices)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "author", "content_text", "status", "created_at", "replies", "can_delete"]

    def get_author(self, obj) -> dict:
        return person(obj.user)

    def get_replies(self, obj) -> list:
        replies = [r for r in self.context.get("replies", {}).get(obj.pk, [])]
        return CommentSerializer(replies, many=True, context=self.context).data

    def get_can_delete(self, obj) -> bool:
        user = self.context["request"].user
        return user.is_authenticated and (obj.user_id == user.pk or self.context.get("can_moderate", False))


class CommentCreateSerializer(serializers.Serializer):
    content_text = serializers.CharField(max_length=2000)
    parent_comment_id = serializers.IntegerField(required=False, allow_null=True)

