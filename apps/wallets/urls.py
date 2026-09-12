from django.urls import path

from .views import WalletListCreateView

urlpatterns = [
    path("", WalletListCreateView.as_view(), name="wallet-list-create"),
]
