import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.users.factories import make_user
from apps.wallets.factories import make_wallet


def transfer_payload(from_wallet, to_wallet, amount):
    return {"from_wallet": str(from_wallet.id), "to_wallet": str(to_wallet.id), "amount": amount}


@pytest.mark.django_db
class TestIdempotency:
    def test_repeated_request_with_same_key_replays_the_response(self):
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=10000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()
        client.force_authenticate(user=sender)
        payload = transfer_payload(from_wallet, to_wallet, 1000)

        first = client.post(
            "/api/v1/ledger/transfers/", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-1"
        )
        second = client.post(
            "/api/v1/ledger/transfers/", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-1"
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.data["id"] == second.data["id"]

        from_wallet.refresh_from_db()
        assert from_wallet.balance == 9000  # debited exactly once, not twice

    def test_same_key_with_a_different_payload_is_rejected(self):
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=10000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()
        client.force_authenticate(user=sender)

        client.post(
            "/api/v1/ledger/transfers/",
            transfer_payload(from_wallet, to_wallet, 1000),
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-2",
        )
        response = client.post(
            "/api/v1/ledger/transfers/",
            transfer_payload(from_wallet, to_wallet, 9999),
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-2",
        )

        assert response.status_code == 409

    def test_without_a_key_repeated_requests_are_independent(self):
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=10000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        client = APIClient()
        client.force_authenticate(user=sender)
        payload = transfer_payload(from_wallet, to_wallet, 1000)

        client.post("/api/v1/ledger/transfers/", payload, format="json")
        client.post("/api/v1/ledger/transfers/", payload, format="json")

        from_wallet.refresh_from_db()
        assert from_wallet.balance == 8000  # both executed — no key means no dedup


@pytest.mark.django_db(transaction=True)
class TestIdempotencyConcurrency:
    def test_concurrent_requests_with_the_same_key_execute_exactly_once(self):
        """Ported from the manual scratchpad script used to verify commit 7. Proves the
        atomic-insert-based locking in run_idempotently() holds under real concurrent
        requests, not just sequential retries — a broken version of this could let two
        requests both believe they were first and both execute the transfer."""
        sender = make_user()
        receiver = make_user()
        from_wallet = make_wallet(owner=sender, currency="USD", balance=10000)
        to_wallet = make_wallet(owner=receiver, currency="USD", balance=0)
        payload = transfer_payload(from_wallet, to_wallet, 2500)

        results = []
        lock = threading.Lock()

        def fire():
            client = APIClient()
            client.force_authenticate(user=sender)
            try:
                response = client.post(
                    "/api/v1/ledger/transfers/",
                    payload,
                    format="json",
                    HTTP_IDEMPOTENCY_KEY="race-key",
                )
                txn_id = response.data.get("id") if response.status_code == 201 else None
                with lock:
                    results.append((response.status_code, txn_id))
            finally:
                connection.close()

        threads = [threading.Thread(target=fire) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successful_ids = {txn_id for status, txn_id in results if status == 201}
        assert len(successful_ids) == 1, "more than one distinct transaction was created"

        from_wallet.refresh_from_db()
        assert from_wallet.balance == 7500  # debited exactly once
