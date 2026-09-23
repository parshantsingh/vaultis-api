from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.views import liveness, metrics, readiness

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", liveness, name="health-check"),
    path("health/ready/", readiness, name="health-ready"),
    path("metrics", metrics, name="metrics"),
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/wallets/", include("apps.wallets.urls")),
    path("api/v1/ledger/", include("apps.ledger.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
