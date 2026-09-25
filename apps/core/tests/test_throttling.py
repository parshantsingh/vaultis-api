import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.users.factories import make_user
from apps.wallets.factories import make_wallet


@pytest.fixture(autouse=True)
def clean_throttle_state():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def set_rate(monkeypatch):
    def apply(scope, rate):
        monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, scope, rate)

    return apply


def login(client, password="wrong-guess"):
    return client.post(
        "/api/v1/auth/token/",
        {"email": "someone@example.com", "password": password},
        format="json",
    )


@pytest.mark.django_db
class TestLoginThrottle:
    def test_blocks_after_the_limit_with_a_retry_after(self, set_rate):
        set_rate("login", "3/min")
        client = APIClient()

        assert [login(client).status_code for _ in range(3)] == [401, 401, 401]
        blocked = login(client)

        assert blocked.status_code == 429
        assert int(blocked["Retry-After"]) > 0

    def test_correct_credentials_are_blocked_too(self, set_rate):
        """Once throttled, a client can't even find out whether its next guess was right —
        otherwise the limit would only slow guessing down, not stop it."""
        set_rate("login", "2/min")
        make_user(email="someone@example.com", password="real-password-1")
        client = APIClient()
        login(client)
        login(client)

        assert login(client, password="real-password-1").status_code == 429

    def test_limits_are_per_scope(self, set_rate):
        set_rate("register", "1/min")
        set_rate("login", "5/min")
        client = APIClient()

        client.post(
            "/api/v1/users/register/", {"email": "a@example.com", "password": "testpass123"}
        )
        second = client.post(
            "/api/v1/users/register/", {"email": "b@example.com", "password": "testpass123"}
        )

        assert second.status_code == 429
        assert login(client).status_code == 401  # login has its own, separate allowance


@pytest.mark.django_db
class TestTransferThrottle:
    def send(self, api, source, target):
        return api.post(
            "/api/v1/ledger/transfers/",
            {"from_wallet": str(source.id), "to_wallet": str(target.id), "amount": 10},
            format="json",
        )

    def test_blocks_transfers_past_the_limit_and_moves_no_money_when_blocked(self, set_rate):
        set_rate("transfers", "2/min")
        sender, receiver = make_user(), make_user()
        source = make_wallet(owner=sender, currency="USD", balance=1000)
        target = make_wallet(owner=receiver, currency="USD")
        api = APIClient()
        api.force_authenticate(user=sender)

        statuses = [self.send(api, source, target).status_code for _ in range(4)]

        assert statuses == [201, 201, 429, 429]
        source.refresh_from_db()
        assert source.balance == 980

    def test_the_limit_is_per_user_not_global(self, set_rate):
        set_rate("transfers", "1/min")
        receiver = make_user()
        target = make_wallet(owner=receiver, currency="USD")
        results = []
        for _ in range(2):
            sender = make_user()
            source = make_wallet(owner=sender, currency="USD", balance=100)
            api = APIClient()
            api.force_authenticate(user=sender)
            results.append(self.send(api, source, target).status_code)

        assert results == [201, 201]
