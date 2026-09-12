from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    # Never accepted from the request body — pulled from the authenticated request
    # instead, so a client can't create a wallet on someone else's behalf. Because it's
    # a real field on validated_data (not something bolted on in the view afterwards),
    # UniqueTogetherValidator below can actually see it during validation.
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Wallet
        fields = ["id", "owner", "currency", "balance", "created_at"]
        read_only_fields = ["id", "balance", "created_at"]
        # The database constraint on the model already blocks a second wallet in the same
        # currency, but that constraint only fires once the query reaches the database —
        # an unhandled IntegrityError there surfaces as a raw 500. Checking it here at
        # validation time turns it into a normal 400 the client can actually parse.
        validators = [
            UniqueTogetherValidator(
                queryset=Wallet.objects.all(),
                fields=["owner", "currency"],
                message="You already have a wallet in this currency.",
            )
        ]
