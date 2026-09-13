from django.contrib import admin

from .models import IdempotencyKey


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ["key", "user", "status", "response_status", "created_at"]
    list_filter = ["status"]
    search_fields = ["key", "user__email"]
    readonly_fields = [f.name for f in IdempotencyKey._meta.fields]
