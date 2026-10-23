from django.contrib import admin

from .models import Comment, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "group", "trip", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("user", "group", "trip", "location")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("post", "user", "parent_comment")
