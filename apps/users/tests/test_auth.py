import pytest
from rest_framework.test import APIClient

from apps.users.factories import UserFactory
from apps.users.models import User


@pytest.mark.django_db
class TestRegistration:
    def test_register_creates_user_with_hashed_password(self):
        client = APIClient()
        response = client.post(
            "/api/v1/users/register/",
            {"email": "new@test.com", "password": "testpass123", "full_name": "New User"},
        )
        assert response.status_code == 201
        assert "password" not in response.data

        user = User.objects.get(email="new@test.com")
        assert user.check_password("testpass123")
        assert user.password != "testpass123"

    def test_login_flow_works_end_to_end_with_a_real_jwt(self):
        client = APIClient()
        client.post(
            "/api/v1/users/register/",
            {"email": "login@test.com", "password": "testpass123"},
        )

        token_response = client.post(
            "/api/v1/auth/token/",
            {"email": "login@test.com", "password": "testpass123"},
        )
        assert token_response.status_code == 200
        access = token_response.data["access"]

        response = client.get("/api/v1/users/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        assert response.status_code == 200
        assert response.data["email"] == "login@test.com"


@pytest.mark.django_db
class TestMe:
    def test_me_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 401

    def test_me_returns_the_authenticated_users_profile(self):
        user = UserFactory(email="me@test.com")
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/v1/users/me/")

        assert response.status_code == 200
        assert response.data["email"] == "me@test.com"
        assert response.data["role"] == "customer"
