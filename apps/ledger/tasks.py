from celery import shared_task

from .reconciliation import run_reconciliation


@shared_task(name="apps.ledger.tasks.reconcile_ledger")
def reconcile_ledger() -> dict[str, object]:
    run = run_reconciliation()
    return {
        "run_id": str(run.id),
        "clean": run.is_clean,
        "wallet_mismatches": run.wallet_mismatches,
        "unbalanced_transactions": run.unbalanced_transactions,
    }
