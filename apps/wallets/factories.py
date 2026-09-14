from typing import Any, cast

import factory

from apps.users.factories import UserFactory

from .models import Currency, Wallet


class WalletFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Wallet

    owner = factory.SubFactory(UserFactory)
    currency = Currency.USD
    balance = 0


def make_wallet(**kwargs: Any) -> Wallet:
    """Typed wrapper around WalletFactory. factory_boy's runtime magic makes
    WalletFactory(...) actually return a Wallet instance, but its type stubs don't
    describe that — mypy sees the call as constructing a WalletFactory, not a Wallet.
    This is the one place that gap is bridged, instead of every test needing its own
    cast() or type: ignore wherever a Wallet-specific attribute is used afterward."""
    return cast(Wallet, WalletFactory(**kwargs))
