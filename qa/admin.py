from django.contrib import admin

from .models import Answer, Question


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    raw_id_fields = ("author",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "author", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "body")
    raw_id_fields = ("author", "location", "accepted_answer", "last_edited_by")
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("question", "author")
