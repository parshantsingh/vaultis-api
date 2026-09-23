import logging
import re
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .logs import request_id_var

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
