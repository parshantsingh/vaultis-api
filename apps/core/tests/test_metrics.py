import pytest
from prometheus_client import REGISTRY
from rest_framework.test import APIClient

from apps.users.factories import make_user
from apps.wallets.factories import make_wallet


def sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0


class TestMetricsEndpointAccess:
    def test_is_disabled_when_no_token_is_set_and_debug_is_off(self, client, settings):
        settings.METRICS_TOKEN = ""
        settings.DEBUG = False
        assert client.get("/metrics").status_code == 404

    def test_is_open_without_a_token_only_in_debug(self, client, settings):
        settings.METRICS_TOKEN = ""
        settings.DEBUG = True
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "vaultis_http_requests_total" in response.content.decode()

    def test_requires_the_bearer_token_when_one_is_configured(self, client, settings):
        settings.METRICS_TOKEN = "s3cret-token"
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        good = client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
        assert good.status_code == 200

    def test_a_non_ascii_authorization_header_is_rejected_not_a_server_error(
        self, client, settings
    ):
        """hmac.compare_digest raises TypeError on a str with non-ASCII characters — a
        client could trigger a 500 on purpose if the comparison weren't done on bytes."""
        settings.METRICS_TOKEN = "s3cret-token"
        response = client.get("/metrics", headers={"Authorization": "Bearer tökén"})
        assert response.status_code == 401


class TestHttpMetrics:
    def test_counts_requests_by_route_template_and_status(self, client):
        before = sample(
            "vaultis_http_requests_total",
            method="GET",
            route="api/v1/users/me/",
            status="401",
        )
        client.get("/api/v1/users/me/")
        after = sample(
            "vaultis_http_requests_total",
            method="GET",
            route="api/v1/users/me/",
            status="401",
        )
        assert after == before + 1

    def test_unmatched_urls_share_one_label_instead_of_one_series_each(self, client):
        """A label per distinct URL would create a new time series for every path anyone
        ever requests — unbounded cardinality that eventually overwhelms Prometheus."""
        labels = {"method": "GET", "route": "unmatched", "status": "404"}
        before = sample("vaultis_http_requests_total", **labels)
        client.get("/definitely/not/a/route/aaa")
        client.get("/definitely/not/a/route/bbb")
        assert sample("vaultis_http_requests_total", **labels) == before + 2

        raw_paths = [
            s.labels["route"]
            for m in REGISTRY.collect()
            for s in m.samples
            if m.name == "vaultis_http_requests"
        ]
        assert not any("definitely" in route for route in raw_paths)

    def test_the_metrics_endpoint_does_not_count_itself(self, client, settings):
        settings.DEBUG = True
        settings.METRICS_TOKEN = ""
        before = sample("vaultis_http_requests_total", method="GET", route="metrics", status="200")
        client.get("/metrics")
        client.get("/metrics")
        after = sample("vaultis_http_requests_total", method="GET", route="metrics", status="200")
        assert after == before


@pytest.mark.django_db
class TestTransferMetrics:
    def make_transfer(self, balance, amount):
        sender, receiver = make_user(), make_user()
        source = make_wallet(owner=sender, currency="USD", balance=balance)
        target = make_wallet(owner=receiver, currency="USD")
        api = APIClient()
        api.force_authenticate(user=sender)
        return lambda: api.post(
            "/api/v1/ledger/transfers/",
            {"from_wallet": str(source.id), "to_wallet": str(target.id), "amount": amount},
            format="json",
        )

    def test_completed_transfer_is_counted_only_after_commit(
        self, django_capture_on_commit_callbacks
    ):
        before = sample("vaultis_transfers_total", outcome="completed")
        send = self.make_transfer(balance=1000, amount=100)

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            send()
        assert sample("vaultis_transfers_total", outcome="completed") == before

        for callback in callbacks:
            callback()
        assert sample("vaultis_transfers_total", outcome="completed") == before + 1

    def test_rejected_transfer_is_counted_by_reason(self):
        before = sample("vaultis_transfers_total", outcome="insufficient_funds")
        self.make_transfer(balance=10, amount=5000)()
        assert sample("vaultis_transfers_total", outcome="insufficient_funds") == before + 1
