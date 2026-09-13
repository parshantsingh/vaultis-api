import pytest
from rest_framework.test import APIClient

from apps.users.factories import UserFactory
from apps.wallets.factories import WalletFactory


@pytest.mark.django_db
class TestWalletCreation:
    def test_create_wallet_starts_at_zero_balance(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post("/api/v1/wallets/", {"currency": "USD"})

        assert response.status_code == 201
        assert response.data["balance"] == 0

    def test_duplicate_currency_returns_400_not_500(self):
        """Regression test for a real bug (commit 4): the database's UniqueConstraint
        on (owner, currency) correctly blocked a second wallet in the same currency, but
        nothing translated that rejection into a clean API response — it surfaced as an
        unhandled 500 (IntegrityError). Fixed with a UniqueTogetherValidator that checks
        before attempting the write. This test exists so that bug can't come back
        unnoticed."""
        user = UserFactory()
        WalletFactory(owner=user, currency="USD")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post("/api/v1/wallets/", {"currency": "USD"})

        assert response.status_code == 400
        assert "already have a wallet" in str(response.data).lower()

    def test_different_currency_is_allowed(self):
        user = UserFactory()
        WalletFactory(owner=user, currency="USD")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post("/api/v1/wallets/", {"currency": "EUR"})

        assert response.status_code == 201


@pytest.mark.django_db
class TestWalletListing:
    def test_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/v1/wallets/")
        assert response.status_code == 401

    def test_only_shows_the_requesting_users_own_wallets(self):
        user = UserFactory()
        other_user = UserFactory()
        WalletFactory(owner=other_user, currency="USD")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/v1/wallets/")

        assert response.data["count"] == 0
