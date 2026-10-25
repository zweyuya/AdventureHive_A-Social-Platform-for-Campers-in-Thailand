from rest_framework import serializers

from core.people import person as _person

from accounts.models import User

from .models import CampingGroup, GroupMember, GroupMemberRole


class GroupSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField(
        help_text="Your role if you are an active member, otherwise null.")

    class Meta:
        model = CampingGroup
        fields = ["id", "name", "description", "category", "privacy_type", "member_count",
                  "created_by", "created_at", "my_role"]
        read_only_fields = ["member_count", "created_at"]

    def get_created_by(self, obj) -> dict:
        return _person(obj.created_by)

    def get_my_role(self, obj) -> str | None:
        return self.context.get("my_roles", {}).get(obj.pk)


class GroupWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampingGroup
        fields = ["name", "description", "category", "privacy_type"]


class MemberSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = GroupMember
        fields = ["user", "role_in_group", "status", "joined_at"]

    def get_user(self, obj) -> dict:
        return _person(obj.user)


class AddMemberSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(status="active", deleted_at__isnull=True), source="user")


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=GroupMemberRole.choices)
