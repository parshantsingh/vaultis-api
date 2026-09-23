import logging
import re
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .logs import request_id_var
from .metrics import HTTP_LATENCY, HTTP_REQUESTS

logger = logging.getLogger("vaultis.request")

# The header value comes from the client and ends up in log lines, so anything that
# isn't a short, plain token is discarded rather than trusted.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_UNLOGGED_PREFIXES = ("/health/",)


class RequestContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex

        # Not reset here: Django logs 4xx responses from its outer handler, after this
        # middleware has already returned, and those lines need the id too. It's cleared
        # by the request_finished signal instead (see CoreConfig.ready).
        request_id_var.set(request_id)
        started = time.monotonic()

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        if not request.path.startswith(_UNLOGGED_PREFIXES):
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 1),
                },
            )
        return response


class MetricsMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path == "/metrics":
            return self.get_response(request)

        started = time.monotonic()
        response = self.get_response(request)
        elapsed = time.monotonic() - started

        # The route *template* ("api/v1/wallets/"), never the raw path. A label value per
        # distinct URL would create a new time series for every id anyone ever requests
        # and eventually overwhelm Prometheus. Unmatched URLs (404s from scanners and
        # typos) all collapse into one bucket for the same reason.
        match = request.resolver_match
        route = match.route if match and match.route else "unmatched"

        HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, route).observe(elapsed)
        return response
