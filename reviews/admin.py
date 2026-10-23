from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("location", "user", "trip", "rating", "status", "created_at")
    list_filter = ("status", "rating")
    raw_id_fields = ("location", "trip", "user")
