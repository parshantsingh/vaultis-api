from django.contrib import admin

from .models import LedgerEntry, ReconciliationRun, Transaction


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


@admin.register(ReconciliationRun)
class ReconciliationRunAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "finished_at",
        "wallet_mismatches",
        "unbalanced_transactions",
        "wallets_checked",
    ]
    readonly_fields = [f.name for f in ReconciliationRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
