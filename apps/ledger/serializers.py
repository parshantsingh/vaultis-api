from rest_framework import serializers

from apps.wallets.models import Wallet

from .models import LedgerEntry, Transaction


class TransferSerializer(serializers.Serializer):
    from_wallet = serializers.PrimaryKeyRelatedField(queryset=Wallet.objects.all())
    to_wallet = serializers.PrimaryKeyRelatedField(queryset=Wallet.objects.all())
    amount = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        request = self.context["request"]
        if attrs["from_wallet"].owner_id != request.user.id:
            raise serializers.ValidationError("You can only transfer from your own wallet.")
        return attrs


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "wallet", "amount"]


class TransactionSerializer(serializers.ModelSerializer):
    entries = LedgerEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Transaction
        fields = ["id", "created_at", "entries"]
