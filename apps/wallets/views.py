from rest_framework import generics, permissions

from .models import Wallet
from .serializers import WalletSerializer


class WalletListCreateView(generics.ListCreateAPIView):
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wallet.objects.filter(owner=self.request.user)
