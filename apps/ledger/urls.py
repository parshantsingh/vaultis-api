from django.urls import path

from .views import TransferView, WalletEntryListView

urlpatterns = [
    path("transfers/", TransferView.as_view(), name="transfer-create"),
    path(
        "wallets/<uuid:wallet_id>/entries/",
        WalletEntryListView.as_view(),
        name="wallet-entries",
    ),
]
