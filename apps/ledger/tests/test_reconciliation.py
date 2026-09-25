import logging

import pytest
from django.conf import settings

from apps.ledger import reconciliation
from apps.ledger.models import LedgerEntry, ReconciliationRun, Transaction
from apps.ledger.services import transfer_funds
from apps.ledger.tasks import reconcile_ledger
from apps.users.factories import make_user
from apps.wallets.factories import make_wallet
from config.celery import app as celery_app


def add_entry(wallet, amount, transaction=None):
    return LedgerEntry.objects.create(
        transaction=transaction or Transaction.objects.create(), wallet=wallet, amount=amount
    )


@pytest.mark.django_db
class TestReconciliation:
    def test_an_empty_ledger_is_clean(self):
        run = reconciliation.run_reconciliation()

        assert run.is_clean
        assert (run.wallets_checked, run.transactions_checked) == (0, 0)
        assert run.finished_at is not None

    def test_a_ledger_built_through_the_service_reconciles_cleanly(self):
        """Balances only ever change alongside matching ledger entries, so a ledger built
        correctly must always come out clean — including the funding step, which in real
        double-entry terms debits a counterparty account rather than creating money."""
        source = make_wallet(owner=make_user(), currency="USD", balance=1000)
        target = make_wallet(owner=make_user(), currency="USD", balance=0)
        bank = make_wallet(owner=make_user(), currency="USD", balance=-1000)
        funding = Transaction.objects.create()
        add_entry(source, 1000, funding)
        add_entry(bank, -1000, funding)
        transfer_funds(from_wallet_id=source.id, to_wallet_id=target.id, amount=300)
        transfer_funds(from_wallet_id=target.id, to_wallet_id=source.id, amount=50)

        run = reconciliation.run_reconciliation()

        assert run.is_clean
        assert (run.wallets_checked, run.transactions_checked) == (3, 3)

    def test_detects_a_balance_changed_without_a_ledger_entry(self):
        wallet = make_wallet(owner=make_user(), currency="USD", balance=500)

        run = reconciliation.run_reconciliation()

        assert not run.is_clean
        assert run.wallet_mismatches == 1
        assert run.details["wallet_mismatches"] == [
            {"wallet": str(wallet.id), "stored_balance": 500, "ledger_total": 0}
        ]

    def test_detects_a_transaction_whose_entries_do_not_sum_to_zero(self):
        first = make_wallet(owner=make_user(), currency="USD", balance=100)
        second = make_wallet(owner=make_user(), currency="USD", balance=-50)
        txn = Transaction.objects.create()
        add_entry(first, 100, txn)
        add_entry(second, -50, txn)  # wallet balances match their entries; the pair doesn't cancel

        run = reconciliation.run_reconciliation()

        assert run.wallet_mismatches == 0
        assert run.unbalanced_transactions == 1
        assert run.details["unbalanced_transactions"] == [
            {"transaction": str(txn.id), "entries_sum": 50}
        ]

    def test_counts_are_exact_but_details_are_capped(self, monkeypatch):
        monkeypatch.setattr(reconciliation, "MAX_DETAILS", 2)
        for _ in range(3):
            make_wallet(owner=make_user(), currency="USD", balance=1)

        run = reconciliation.run_reconciliation()

        assert run.wallet_mismatches == 3
        assert len(run.details["wallet_mismatches"]) == 2

    def test_every_run_is_kept_as_its_own_record(self):
        reconciliation.run_reconciliation()
        reconciliation.run_reconciliation()
        assert ReconciliationRun.objects.count() == 2


@pytest.mark.django_db
class TestReconciliationLogging:
    def test_clean_run_logs_info(self, caplog):
        with caplog.at_level(logging.INFO, logger="apps.ledger.reconciliation"):
            reconciliation.run_reconciliation()

        record = caplog.records[-1]
        assert (record.levelname, record.message) == ("INFO", "ledger reconciliation clean")

    def test_discrepancies_log_at_error_level(self, caplog):
        make_wallet(owner=make_user(), currency="USD", balance=500)

        with caplog.at_level(logging.INFO, logger="apps.ledger.reconciliation"):
            reconciliation.run_reconciliation()

        record = caplog.records[-1]
        assert record.levelname == "ERROR"
        assert record.wallet_mismatches == 1


@pytest.mark.django_db
class TestCeleryWiring:
    def test_the_task_returns_a_json_serialisable_summary(self):
        make_wallet(owner=make_user(), currency="USD", balance=500)

        summary = reconcile_ledger()

        assert summary["clean"] is False
        assert summary["wallet_mismatches"] == 1
        assert ReconciliationRun.objects.filter(id=summary["run_id"]).exists()

    def test_the_task_is_registered_with_celery(self):
        celery_app.loader.import_default_modules()
        assert "apps.ledger.tasks.reconcile_ledger" in celery_app.tasks

    def test_every_scheduled_task_name_actually_exists(self):
        """A typo in CELERY_BEAT_SCHEDULE fails silently: beat happily sends a task name
        no worker has, and the only symptom is an error in the worker's log."""
        celery_app.loader.import_default_modules()
        for name, entry in settings.CELERY_BEAT_SCHEDULE.items():
            assert entry["task"] in celery_app.tasks, f"{name} points at an unregistered task"
