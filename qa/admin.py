from django.contrib import admin, messages

from . import services
from .models import Answer, Question


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ("author", "body", "status", "created_at", "edited_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "author", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "body")
    readonly_fields = ("author", "location", "title", "body", "status", "accepted_answer",
                       "created_at", "edited_at", "last_edited_by")
    inlines = [AnswerInline]
    actions = ["hide_selected", "restore_selected"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Hide selected questions")
    def hide_selected(self, request, queryset):
        for q in queryset:
            services.set_question_hidden(q, True)
        self.message_user(request, f"Hid {queryset.count()} question(s).", messages.SUCCESS)

    @admin.action(description="Restore selected questions")
    def restore_selected(self, request, queryset):
        for q in queryset:
            services.set_question_hidden(q, False)
        self.message_user(request, f"Restored {queryset.count()} question(s).", messages.SUCCESS)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("body",)
    readonly_fields = ("question", "author", "body", "status", "created_at", "edited_at")
    actions = ["hide_selected", "restore_selected"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Hide selected answers")
    def hide_selected(self, request, queryset):
        for a in queryset:
            services.set_answer_hidden(a, True)
        self.message_user(request, f"Hid {queryset.count()} answer(s).", messages.SUCCESS)

    @admin.action(description="Restore selected answers")
    def restore_selected(self, request, queryset):
        for a in queryset:
            services.set_answer_hidden(a, False)
        self.message_user(request, f"Restored {queryset.count()} answer(s).", messages.SUCCESS)
