import logging

from django.db.models import BigIntegerField, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.wallets.models import Wallet

from .models import ReconciliationRun, Transaction

logger = logging.getLogger(__name__)

# The counts on the run are exact; the details are only a sample, so one badly broken
# ledger can't produce an unboundedly large row.
MAX_DETAILS = 100


def run_reconciliation() -> ReconciliationRun:
    """Check the two invariants the ledger relies on and record the outcome.

    1. Every wallet's stored balance equals the sum of its ledger entries. The balance is
       a cached figure, written in the same DB transaction as the entries; if the two ever
       disagree, something changed a balance without going through the ledger.
    2. Every transaction's entries sum to zero (money moved, none created or destroyed).
    """
    run = ReconciliationRun.objects.create()

    mismatched_wallets = list(
        Wallet.objects.annotate(
            ledger_total=Coalesce(Sum("ledger_entries__amount"), 0, output_field=BigIntegerField())
        )
        .exclude(balance=F("ledger_total"))
        .values("id", "balance", "ledger_total")
    )
    unbalanced = list(
        Transaction.objects.annotate(
            total=Coalesce(Sum("entries__amount"), 0, output_field=BigIntegerField())
        )
        .exclude(total=0)
        .values("id", "total")
    )

    run.wallets_checked = Wallet.objects.count()
    run.transactions_checked = Transaction.objects.count()
    run.wallet_mismatches = len(mismatched_wallets)
    run.unbalanced_transactions = len(unbalanced)
    run.details = {
        "wallet_mismatches": [
            {
                "wallet": str(w["id"]),
                "stored_balance": w["balance"],
                "ledger_total": w["ledger_total"],
            }
            for w in mismatched_wallets[:MAX_DETAILS]
        ],
        "unbalanced_transactions": [
            {"transaction": str(t["id"]), "entries_sum": t["total"]}
            for t in unbalanced[:MAX_DETAILS]
        ],
    }
    run.finished_at = timezone.now()
    run.save()

    counts = {
        "run_id": str(run.id),
        "wallets_checked": run.wallets_checked,
        "transactions_checked": run.transactions_checked,
        "wallet_mismatches": run.wallet_mismatches,
        "unbalanced_transactions": run.unbalanced_transactions,
    }
    if run.is_clean:
        logger.info("ledger reconciliation clean", extra=counts)
    else:
        # ERROR, not WARNING: this means money records disagree with each other, which is
        # the kind of thing that should page someone once alerting exists.
        logger.error("ledger reconciliation found discrepancies", extra=counts)
    return run
