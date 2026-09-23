import hmac
import logging

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

logger = logging.getLogger(__name__)


def liveness(request: HttpRequest) -> JsonResponse:
    """Answers whether the process is up at all — deliberately touches nothing else, so
    an orchestrator restarting on failure doesn't restart the app just because the
    database is briefly unreachable."""
    return JsonResponse({"status": "ok"})


def readiness(request: HttpRequest) -> JsonResponse:
    """Answers whether this instance can actually serve traffic right now."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("readiness check failed")
        return JsonResponse({"status": "unavailable", "database": "down"}, status=503)
    return JsonResponse({"status": "ok", "database": "up"})


def metrics(request: HttpRequest) -> HttpResponse:
    """Prometheus scrape endpoint. Exposes request rates, routes, and business volumes,
    so it isn't left open: with METRICS_TOKEN set it requires that bearer token; with
    none configured it's only reachable while DEBUG is on, and 404s otherwise."""
    if settings.METRICS_TOKEN:
        supplied = request.headers.get("Authorization", "").encode()
        expected = f"Bearer {settings.METRICS_TOKEN}".encode()
        # Constant-time comparison, and on bytes: compare_digest raises TypeError on a
        # str containing non-ASCII characters, which a client could send on purpose.
        if not hmac.compare_digest(supplied, expected):
            return HttpResponse(status=401)
    elif not settings.DEBUG:
        raise Http404

    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
