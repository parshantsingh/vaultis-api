from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.core.models import BaseModel

from .managers import UserManager


class Role(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    MERCHANT = "merchant", "Merchant"
    ADMIN = "admin", "Admin"


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    # Log in with email; Django's default expects a username field, which this model doesn't have.
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def is_merchant(self):
        return self.role == Role.MERCHANT
