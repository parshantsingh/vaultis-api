import factory

from apps.users.factories import UserFactory

from .models import Currency, Wallet


class WalletFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Wallet

    owner = factory.SubFactory(UserFactory)
    currency = Currency.USD
    balance = 0
