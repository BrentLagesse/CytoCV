"""Custom user model for CytoCV."""

from __future__ import annotations

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from core.config import default_process_config


class CustomUserManager(BaseUserManager):
    """Manager for creating users with email as the identifier."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """Create and save a user with the given email and password.

        Args:
            email: User email address (required).
            password: Raw password to hash, or None to set an unusable password.
            **extra_fields: Additional model fields.

        Returns:
            The created user instance.

        Raises:
            ValueError: If the email is missing.
        """
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Create a standard user."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        """Create a superuser with elevated permissions."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """User model with storage and processing quota tracking."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Email is the unique identifier for authentication.
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    total_storage = models.PositiveIntegerField(default=1024 * 1024 * 1024)  # 1 GB
    available_storage = models.IntegerField(default=1024 * 1024 * 1024)  # 1 GB
    used_storage = models.IntegerField(default=0)
    processing_used = models.FloatField(default=0)  # in seconds
    config = models.JSONField(default=default_process_config)

    objects = CustomUserManager()

    # Use email as the unique identifier for authentication.
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:
        """Return the primary identifier for display."""
        return self.email

