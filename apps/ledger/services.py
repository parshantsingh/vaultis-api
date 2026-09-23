import logging

from django.db import transaction as db_transaction
from django.db.models import Sum

from apps.wallets.models import Wallet

from .exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
    LedgerIntegrityError,
    SameWalletError,
)
from .models import LedgerEntry, Transaction

logger = logging.getLogger(__name__)


@db_transaction.atomic
def transfer_funds(*, from_wallet_id, to_wallet_id, amount):
    if from_wallet_id == to_wallet_id:
        raise SameWalletError("Cannot transfer a wallet to itself.")

    # Lock both wallet rows for the rest of this DB transaction, always in the same
    # (id-sorted) order regardless of transfer direction. Without this, two transfers
    # crossing each other (A->B and B->A at the same moment) could each hold one lock
    # while waiting on the other — a deadlock. A fixed lock order makes that impossible:
    # whichever transfer's query runs first always acquires both locks before the second
    # transfer can acquire either one.
    wallets = {
        wallet.id: wallet
        for wallet in Wallet.objects.select_for_update()
        .filter(id__in=[from_wallet_id, to_wallet_id])
        .order_by("id")
    }
    from_wallet = wallets[from_wallet_id]
    to_wallet = wallets[to_wallet_id]

    if from_wallet.currency != to_wallet.currency:
        raise CurrencyMismatchError("Cannot transfer between wallets in different currencies.")
    if from_wallet.balance < amount:
        raise InsufficientFundsError("Insufficient balance for this transfer.")

    txn = Transaction.objects.create()
    LedgerEntry.objects.create(transaction=txn, wallet=from_wallet, amount=-amount)
    LedgerEntry.objects.create(transaction=txn, wallet=to_wallet, amount=amount)

    total = txn.entries.aggregate(total=Sum("amount"))["total"]
    if total != 0:
        raise LedgerIntegrityError(f"Transaction {txn.id} entries sum to {total}, not zero.")

    from_wallet.balance -= amount
    to_wallet.balance += amount
    from_wallet.save(update_fields=["balance", "updated_at"])
    to_wallet.save(update_fields=["balance", "updated_at"])

    # on_commit, not a plain call: this line should only exist if the database
    # transaction actually committed, not if something later rolled it back.
    db_transaction.on_commit(
        lambda: logger.info(
            "transfer completed",
            extra={
                "transaction_id": str(txn.id),
                "from_wallet": str(from_wallet.id),
                "to_wallet": str(to_wallet.id),
                "amount": amount,
                "currency": from_wallet.currency,
            },
        )
    )

    return txn
