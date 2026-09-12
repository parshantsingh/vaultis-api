from django.contrib import admin

from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["owner", "currency", "balance", "created_at"]
    list_filter = ["currency"]
    search_fields = ["owner__email"]
    readonly_fields = ["id", "balance", "created_at", "updated_at"]
