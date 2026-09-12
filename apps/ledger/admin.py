from django.contrib import admin

from .models import LedgerEntry, Transaction


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    readonly_fields = ["id", "wallet", "amount", "created_at"]
    can_delete = False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [LedgerEntryInline]
