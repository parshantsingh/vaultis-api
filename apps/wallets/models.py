from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Currency(models.TextChoices):
    USD = "USD", "US Dollar"
    INR = "INR", "Indian Rupee"
    EUR = "EUR", "Euro"


class Wallet(BaseModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallets",
    )
    currency = models.CharField(max_length=3, choices=Currency.choices)

    # Minor units (cents, paise) as an integer, never a float — floats can't represent
    # money exactly, and a few cents of drift is unacceptable in a ledger. This field is
    # only ever changed by the ledger app (next commit), never written directly from a view.
    balance = models.BigIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "currency"], name="one_wallet_per_currency"),
        ]

    def __str__(self):
        return f"{self.owner.email} · {self.currency}"
