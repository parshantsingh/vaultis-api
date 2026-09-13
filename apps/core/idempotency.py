import hashlib
import json

from django.db import IntegrityError
from django.db import transaction as db_transaction
from rest_framework.response import Response

from .models import IdempotencyKey


def run_idempotently(*, user, key, fingerprint, operation):
    """Run `operation()` (a no-arg callable returning a DRF Response) at most once per
    (user, key) pair.

    `fingerprint` is a JSON-serializable value describing what this specific request is
    asking for (e.g. {"from_wallet": "...", "amount": 500}) — it's what lets a genuine
    retry (same key, same request) be told apart from the same key being reused by
    mistake for a materially different request, which is rejected rather than replayed.

    If `key` is falsy, idempotency is skipped entirely and `operation()` just runs —
    the header is opt-in, not mandatory, matching how the roadmap describes it.
    """
    if not key:
        return operation()

    fingerprint_hash = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()

    # A direct insert attempt, not a "check if it exists, then insert" — two requests
    # racing here can't both believe they're first. Whichever INSERT wins the database's
    # unique constraint on (user, key) proceeds; the other gets IntegrityError and falls
    # into the branch below instead. This is the same class of fix as the wallet
    # duplicate-currency bug from an earlier commit, applied correctly from the start.
    try:
        with db_transaction.atomic():
            record = IdempotencyKey.objects.create(
                user=user,
                key=key,
                request_hash=fingerprint_hash,
                status=IdempotencyKey.Status.PROCESSING,
            )
    except IntegrityError:
        record = IdempotencyKey.objects.get(user=user, key=key)
        if record.request_hash != fingerprint_hash:
            return Response(
                {"detail": "This Idempotency-Key was already used with a different request."},
                status=409,
            )
        if record.status == IdempotencyKey.Status.PROCESSING:
            return Response(
                {"detail": "A request with this Idempotency-Key is already being processed."},
                status=409,
            )
        return Response(record.response_body, status=record.response_status)

    try:
        response = operation()
    except Exception:
        # Nothing succeeded — delete the claim so a genuine retry (e.g. after fixing
        # insufficient funds) can run fresh, rather than being permanently stuck behind
        # a failed attempt. Only a response that actually happened gets cached below.
        record.delete()
        raise

    try:
        record.status = IdempotencyKey.Status.COMPLETED
        record.response_status = response.status_code
        record.response_body = response.data
        record.save(update_fields=["status", "response_status", "response_body", "updated_at"])
    except Exception:
        # The operation itself already succeeded at this point — a failure here is a
        # bookkeeping problem, not a reason to tell the client their request failed.
        # Delete the record rather than leave it wedged at PROCESSING forever, which
        # would silently block every future retry of this key with a 409 that never
        # resolves. Still return the real (successful) response below.
        record.delete()

    return response
