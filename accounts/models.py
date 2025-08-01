import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from core.config import DEFAULT_PROCESS_CONFIG

def get_default_config():
    return DEFAULT_PROCESS_CONFIG

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # maximum storage, placeholder for now
    # will be CHANGED when deploy to cloud
    # the storage unit is byte
    total_storage = models.PositiveIntegerField(default=1024 * 1024 * 1024) # 1 GB
    available_storage = models.IntegerField(default=1024 * 1024 * 1024)  # 1 GB
    used_storage = models.IntegerField(default=0)
    processing_used = models.FloatField(default=0) # in seconds
    config = models.JSONField(default=get_default_config)


