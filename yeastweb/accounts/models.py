"""Custom user model for Yeast-Web."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from core.config import default_process_config


class CustomUser(AbstractUser):
    """User model with storage and processing quota tracking."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    total_storage = models.PositiveIntegerField(default=1024 * 1024 * 1024)  # 1 GB
    available_storage = models.IntegerField(default=1024 * 1024 * 1024)  # 1 GB
    used_storage = models.IntegerField(default=0)
    processing_used = models.FloatField(default=0)  # in seconds
    config = models.JSONField(default=default_process_config)


