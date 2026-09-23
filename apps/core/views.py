import logging

from django.db import connection
from django.http import HttpRequest, JsonResponse

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
