import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class UUIDModel(models.Model):
    # Sequential integer IDs let anyone guess adjacent records (/wallets/104/, /wallets/105/).
    # For financial records that's an enumeration risk, so every domain model uses a UUID instead.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class IdempotencyKey(BaseModel):
    """Records that a given (user, key) pair has already been used for a mutating
    request, so a retried request replays the original response instead of re-running
    whatever it did. Deliberately separate from any one app (wallets/ledger) since any
    future mutating endpoint can reuse the same mechanism."""

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    # CASCADE, unlike Wallet/LedgerEntry's PROTECT: this is a request-dedup cache, not a
    # financial record — nothing is lost by letting it disappear with the user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="idempotency_keys",
    )
    key = models.CharField(max_length=255)
    # Hash of the request's meaningful fields — lets a genuine retry (same key, same
    # request) be told apart from the same key accidentally reused for something else.
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    # Plain JSONField uses the stdlib json.JSONEncoder by default, which can't serialize
    # a UUID — and this response body is exactly the kind of payload full of them.
    # DjangoJSONEncoder additionally handles Decimal and date/datetime objects.
    response_body = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="unique_idempotency_key_per_user"),
        ]

    def __str__(self):
        return f"{self.user_id} · {self.key}"
