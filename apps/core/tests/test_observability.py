import json
import logging
from unittest import mock

import pytest
from rest_framework.test import APIClient

from apps.core.logs import JsonFormatter, RequestIdFilter, request_id_var
from apps.users.factories import make_user
from apps.wallets.factories import make_wallet


class TestRequestId:
    def test_generates_an_id_when_none_is_supplied(self, client):
        response = client.get("/health/")
        assert len(response["X-Request-ID"]) == 32

    def test_honours_a_well_formed_client_supplied_id(self, client):
        response = client.get("/health/", headers={"X-Request-ID": "trace-abc.123"})
        assert response["X-Request-ID"] == "trace-abc.123"

    @pytest.mark.parametrize("bad_id", ['has space"}{', "x" * 65, "new\nline"])
    def test_replaces_a_malformed_client_supplied_id(self, client, bad_id):
        """The header is client-controlled and ends up in log lines — anything that
        isn't a short plain token must be discarded, not echoed into the logs."""
        response = client.get("/health/", headers={"X-Request-ID": bad_id})
        assert response["X-Request-ID"] != bad_id
        assert len(response["X-Request-ID"]) == 32

    def test_is_cleared_after_the_request_finishes(self, client):
        client.get("/health/", headers={"X-Request-ID": "trace-cleanup"})
        assert request_id_var.get() is None


class TestAccessLog:
    def test_logs_one_line_per_request_with_the_request_id(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="vaultis.request"):
            client.get("/api/v1/users/me/", headers={"X-Request-ID": "trace-log"})

        record = next(r for r in caplog.records if r.name == "vaultis.request")
        assert record.request_id == "trace-log"
        assert (record.method, record.path, record.status) == ("GET", "/api/v1/users/me/", 401)

    def test_django_request_warnings_carry_the_id_too(self, client, caplog):
        """Regression test: Django logs 4xx responses from its outer handler, after the
        middleware has returned. Resetting the request id in the middleware itself left
        those lines with request_id=None — exactly the ones worth correlating."""
        with caplog.at_level(logging.WARNING, logger="django.request"):
            client.get("/api/v1/users/me/", headers={"X-Request-ID": "trace-401"})

        record = next(r for r in caplog.records if r.name == "django.request")
        assert record.request_id == "trace-401"

    def test_health_checks_are_not_logged(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="vaultis.request"):
            client.get("/health/")
            client.get("/health/ready/")
        assert not [r for r in caplog.records if r.name == "vaultis.request"]


class TestJsonFormatter:
    def make_record(self, **extra):
        record = logging.LogRecord(
            "some.logger", logging.INFO, "f.py", 1, "hello %s", ("you",), None
        )
        for key, value in extra.items():
            setattr(record, key, value)
        RequestIdFilter().filter(record)
        return record

    def test_emits_valid_json_with_the_standard_fields(self):
        token = request_id_var.set("trace-json")
        try:
            payload = json.loads(JsonFormatter().format(self.make_record()))
        finally:
            request_id_var.reset(token)

        assert payload["level"] == "INFO"
        assert payload["logger"] == "some.logger"
        assert payload["message"] == "hello you"
        assert payload["request_id"] == "trace-json"
        assert "timestamp" in payload

    def test_includes_extra_fields_and_serialises_odd_types(self):
        from uuid import uuid4

        payload = json.loads(JsonFormatter().format(self.make_record(amount=500, txn=uuid4())))
        assert payload["amount"] == 500
        assert isinstance(payload["txn"], str)

    def test_includes_the_traceback_for_exceptions(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord("l", logging.ERROR, "f.py", 1, "failed", (), sys.exc_info())
        payload = json.loads(JsonFormatter().format(record))
        assert "ValueError: boom" in payload["exception"]


@pytest.mark.django_db
class TestHealthEndpoints:
    def test_liveness_needs_no_database(self, client):
        response = client.get("/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_reports_database_up(self, client):
        response = client.get("/health/ready/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "up"}

    def test_readiness_returns_503_when_the_database_is_unreachable(self, client):
        with mock.patch("apps.core.views.connection") as broken:
            broken.cursor.side_effect = Exception("connection refused")
            response = client.get("/health/ready/")

        assert response.status_code == 503
        assert response.json()["database"] == "down"


@pytest.mark.django_db
class TestTransferLogging:
    def test_completed_transfer_is_logged_only_after_commit(
        self, caplog, django_capture_on_commit_callbacks
    ):
        sender, receiver = make_user(), make_user()
        source = make_wallet(owner=sender, currency="USD", balance=1000)
        target = make_wallet(owner=receiver, currency="USD")
        api = APIClient()
        api.force_authenticate(user=sender)

        with caplog.at_level(logging.INFO, logger="apps.ledger.services"):
            with django_capture_on_commit_callbacks(execute=False) as callbacks:
                api.post(
                    "/api/v1/ledger/transfers/",
                    {"from_wallet": str(source.id), "to_wallet": str(target.id), "amount": 400},
                    format="json",
                )
            transfer_logs = [r for r in caplog.records if r.name == "apps.ledger.services"]
            assert not transfer_logs, "logged before the transaction committed"

            for callback in callbacks:
                callback()

        record = next(r for r in caplog.records if r.name == "apps.ledger.services")
        assert record.amount == 400
        assert record.from_wallet == str(source.id)
