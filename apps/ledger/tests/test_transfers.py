import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.users.factories import make_user
from apps.wallets.factories import make_wallet


def transfer_payload(from_wallet, to_wallet, amount):
    return {"from_wallet": str(from_wallet.id), "to_wallet": str(to_wallet.id), "amount": amount}


@pytest.mark.django_db
class TestTransfer:
    def test_successful_transfer_moves_balance_and_writes_matching_entries(self):
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=10000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()
        client.force_authenticate(user=sender)

        response = client.post(
            "/api/v1/ledger/transfers/",
            transfer_payload(from_wallet, to_wallet, 3000),
            format="json",
        )

        assert response.status_code == 201
        amounts = sorted(entry["amount"] for entry in response.data["entries"])
        assert amounts == [-3000, 3000]

        from_wallet.refresh_from_db()
        to_wallet.refresh_from_db()
        assert from_wallet.balance == 7000
        assert to_wallet.balance == 3000

    def test_insufficient_funds_returns_400(self):
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=100)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()
        client.force_authenticate(user=sender)

        response = client.post(
            "/api/v1/ledger/transfers/",
            transfer_payload(from_wallet, to_wallet, 999999),
            format="json",
        )

        assert response.status_code == 400

    def test_cannot_transfer_to_the_same_wallet(self):
        sender = make_user()
        wallet = make_wallet(owner=sender, currency="USD", balance=1000)
        client = APIClient()
        client.force_authenticate(user=sender)

        response = client.post(
            "/api/v1/ledger/transfers/", transfer_payload(wallet, wallet, 100), format="json"
        )

        assert response.status_code == 400

    def test_cannot_transfer_from_a_wallet_you_do_not_own(self):
        owner = make_user()
        attacker = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=owner, currency="USD", balance=1000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()
        client.force_authenticate(user=attacker)

        response = client.post(
            "/api/v1/ledger/transfers/",
            transfer_payload(from_wallet, to_wallet, 100),
            format="json",
        )

        assert response.status_code == 400

    def test_requires_authentication(self):
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=1000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()

        response = client.post(
            "/api/v1/ledger/transfers/",
            transfer_payload(from_wallet, to_wallet, 100),
            format="json",
        )

        assert response.status_code == 401


@pytest.mark.django_db(transaction=True)
class TestTransferConcurrency:
    def test_concurrent_transfers_cannot_overdraft_a_wallet(self):
        """Ported from the manual scratchpad script used to verify commit 6. A wallet
        with 50000 can afford exactly 5 transfers of 10000. Firing 10 simultaneous
        requests proves the row locking in transfer_funds() actually holds under real
        concurrent load — without it, multiple requests could read the same starting
        balance and all succeed, driving the wallet negative."""
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=50000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)

        results = []
        lock = threading.Lock()

        def fire():
            client = APIClient()
            client.force_authenticate(user=sender)
            try:
                response = client.post(
                    "/api/v1/ledger/transfers/",
                    transfer_payload(from_wallet, to_wallet, 10000),
                    format="json",
                )
                with lock:
                    results.append(response.status_code)
            finally:
                # Each thread gets its own DB connection (that's the whole point — see
                # the tutorial). Django only auto-closes connections at the end of an
                # HTTP request/response cycle on the *main* thread; a plain Python
                # thread has no such cycle, so without this the connection is only
                # closed later by garbage collection, which logs a ResourceWarning.
                connection.close()

        threads = [threading.Thread(target=fire) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(201) == 5
        assert results.count(400) == 5

        from_wallet.refresh_from_db()
        to_wallet.refresh_from_db()
        assert from_wallet.balance == 0
        assert to_wallet.balance == 50000
