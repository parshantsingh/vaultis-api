import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.core.idempotency import run_idempotently
from apps.core.metrics import TRANSFERS
from apps.wallets.models import Wallet

from .exceptions import LedgerError
from .models import LedgerEntry
from .serializers import (
    TransactionSerializer,
    TransferSerializer,
    WalletEntrySerializer,
)
from .services import transfer_funds

logger = logging.getLogger(__name__)


class TransferView(GenericAPIView):
    serializer_class = TransferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from_wallet = serializer.validated_data["from_wallet"]
        to_wallet = serializer.validated_data["to_wallet"]
        amount = serializer.validated_data["amount"]

        def do_transfer():
            try:
                txn = transfer_funds(
                    from_wallet_id=from_wallet.id,
                    to_wallet_id=to_wallet.id,
                    amount=amount,
                )
            except LedgerError as exc:
                TRANSFERS.labels(exc.code).inc()
                logger.info(
                    "transfer rejected",
                    extra={
                        "reason": exc.code,
                        "from_wallet": str(from_wallet.id),
                        "to_wallet": str(to_wallet.id),
                        "amount": amount,
                    },
                )
                raise ValidationError(str(exc)) from exc
            return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

        return run_idempotently(
            user=request.user,
            key=request.headers.get("Idempotency-Key"),
            fingerprint={
                "from_wallet": str(from_wallet.id),
                "to_wallet": str(to_wallet.id),
                "amount": amount,
            },
            operation=do_transfer,
        )


class WalletEntryListView(generics.ListAPIView):
    """A wallet's statement: its ledger entries, newest first."""

    serializer_class = WalletEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LedgerEntry.objects.none()

        # 404 for a wallet that doesn't exist and for one owned by someone else alike,
        # so this endpoint can't be used to find out which wallet ids exist.
        wallet = get_object_or_404(Wallet, id=self.kwargs["wallet_id"], owner=self.request.user)
        return LedgerEntry.objects.filter(wallet=wallet).order_by("-created_at", "-id")
