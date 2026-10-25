from django.contrib import admin

from .models import Comment, Post, Reaction


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "group", "trip", "status", "reaction_count", "comment_count", "created_at")
    list_filter = ("status",)
    search_fields = ("content_text",)
    raw_id_fields = ("user", "group", "trip", "location", "reviewed_by")
    readonly_fields = ("reaction_count", "comment_count", "created_at", "edited_at", "reviewed_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("post", "user", "parent_comment")


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "type", "created_at")
    list_filter = ("type",)
    raw_id_fields = ("post", "user")
