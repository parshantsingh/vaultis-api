from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from .exceptions import LedgerError
from .serializers import TransactionSerializer, TransferSerializer
from .services import transfer_funds


class TransferView(GenericAPIView):
    serializer_class = TransferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            txn = transfer_funds(
                from_wallet_id=serializer.validated_data["from_wallet"].id,
                to_wallet_id=serializer.validated_data["to_wallet"].id,
                amount=serializer.validated_data["amount"],
            )
        except LedgerError as exc:
            raise ValidationError(str(exc)) from exc

        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)
