from django.urls import path

from .views import TransferView

urlpatterns = [
    path("transfers/", TransferView.as_view(), name="transfer-create"),
]
