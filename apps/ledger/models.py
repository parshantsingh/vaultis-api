from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.wallets.models import Wallet


class Transaction(BaseModel):
    """One economic event (currently: a transfer). Exists mainly to group the matched
    debit/credit LedgerEntry pair it produces under a single id, for audit/reference."""

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.id)


class LedgerEntry(BaseModel):
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="entries")
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger_entries")

    # Signed minor units: positive = credit (increases the wallet), negative = debit
    # (decreases it). A transfer writes one of each, and the two must sum to zero —
    # enforced in apps/ledger/services.py, inside the same DB transaction as the write,
    # since that invariant spans two rows and a single-row CHECK constraint can't express it.
    amount = models.BigIntegerField()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            # Serves the wallet statement query: one wallet's entries, newest first.
            models.Index(
                fields=["wallet", "-created_at", "-id"], name="ledger_entry_wallet_recent_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name="ledger_entry_amount_nonzero"),
        ]

    def __str__(self):
        return f"{self.transaction_id} · {self.wallet_id} · {self.amount}"
