import logging

from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.core.idempotency import run_idempotently

from .exceptions import LedgerError
from .serializers import TransactionSerializer, TransferSerializer
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
                logger.info(
                    "transfer rejected",
                    extra={
                        "reason": type(exc).__name__,
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
