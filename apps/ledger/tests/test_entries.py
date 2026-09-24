from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.ledger.models import LedgerEntry, Transaction
from apps.users.factories import make_user
from apps.wallets.factories import make_wallet


def entries_url(wallet_id):
    return f"/api/v1/ledger/wallets/{wallet_id}/entries/"


def add_entry(wallet, amount):
    return LedgerEntry.objects.create(
        transaction=Transaction.objects.create(), wallet=wallet, amount=amount
    )


@pytest.fixture
def owner():
    return make_user()


@pytest.fixture
def api(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.mark.django_db
class TestWalletEntries:
    def test_lists_entries_newest_first(self, api, owner):
        wallet = make_wallet(owner=owner, currency="USD")
        first = add_entry(wallet, 100)
        second = add_entry(wallet, -30)
        third = add_entry(wallet, 500)

        response = api.get(entries_url(wallet.id))

        assert response.status_code == 200
        assert [e["id"] for e in response.data["results"]] == [
            str(third.id),
            str(second.id),
            str(first.id),
        ]
        assert response.data["results"][1]["amount"] == -30

    def test_only_includes_that_wallets_entries(self, api, owner):
        wallet = make_wallet(owner=owner, currency="USD")
        other_wallet = make_wallet(owner=owner, currency="EUR")
        mine = add_entry(wallet, 100)
        add_entry(other_wallet, 999)

        response = api.get(entries_url(wallet.id))

        assert [e["id"] for e in response.data["results"]] == [str(mine.id)]

    def test_response_exposes_the_transaction_id(self, api, owner):
        wallet = make_wallet(owner=owner, currency="USD")
        entry = add_entry(wallet, 100)

        result = api.get(entries_url(wallet.id)).data["results"][0]

        assert result["transaction"] == str(entry.transaction_id)

    def test_is_paginated(self, api, owner):
        wallet = make_wallet(owner=owner, currency="USD")
        for _ in range(25):
            add_entry(wallet, 1)

        first_page = api.get(entries_url(wallet.id))
        second_page = api.get(first_page.data["next"])

        assert first_page.data["count"] == 25
        assert len(first_page.data["results"]) == 20
        assert len(second_page.data["results"]) == 5
        first_ids = {e["id"] for e in first_page.data["results"]}
        assert first_ids.isdisjoint(e["id"] for e in second_page.data["results"])

    def test_query_count_does_not_grow_with_the_number_of_entries(
        self, api, owner, django_assert_max_num_queries
    ):
        """Wallet lookup, the pagination count, and the page itself — and nothing per row.
        A serializer that touched a related object per entry would fail this."""
        wallet = make_wallet(owner=owner, currency="USD")
        for _ in range(20):
            add_entry(wallet, 1)

        with django_assert_max_num_queries(3):
            response = api.get(entries_url(wallet.id))

        assert len(response.data["results"]) == 20

    def test_a_real_transfer_shows_up_from_both_sides(self, owner):
        receiver = make_user()
        source = make_wallet(owner=owner, currency="USD", balance=1000)
        target = make_wallet(owner=receiver, currency="USD")
        sender_api = APIClient()
        sender_api.force_authenticate(user=owner)
        receiver_api = APIClient()
        receiver_api.force_authenticate(user=receiver)

        sender_api.post(
            "/api/v1/ledger/transfers/",
            {"from_wallet": str(source.id), "to_wallet": str(target.id), "amount": 250},
            format="json",
        )

        assert sender_api.get(entries_url(source.id)).data["results"][0]["amount"] == -250
        assert receiver_api.get(entries_url(target.id)).data["results"][0]["amount"] == 250


@pytest.mark.django_db
class TestWalletEntriesAccess:
    def test_requires_authentication(self, owner):
        wallet = make_wallet(owner=owner, currency="USD")
        assert APIClient().get(entries_url(wallet.id)).status_code == 401

    def test_someone_elses_wallet_is_a_404_not_a_403(self, api):
        """403 would confirm the wallet exists; 404 makes 'not yours' and 'doesn't exist'
        indistinguishable, so the endpoint can't be used to probe for wallet ids."""
        stranger_wallet = make_wallet(owner=make_user(), currency="USD")
        add_entry(stranger_wallet, 100)

        assert api.get(entries_url(stranger_wallet.id)).status_code == 404

    def test_unknown_wallet_is_a_404(self, api):
        assert api.get(entries_url(uuid4())).status_code == 404
