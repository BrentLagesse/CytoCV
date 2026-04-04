"""Signals that keep effective user quota aligned with policy changes."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.quota import sync_user_quota

CustomUser = get_user_model()
QUOTA_RELEVANT_FIELDS = {"email", "quota_override_mode", "quota_override_bytes"}


@receiver(pre_save, sender=CustomUser)
def capture_previous_quota_state(sender, instance, **_kwargs) -> None:
    """Capture pre-save quota-relevant fields for change detection."""

    if instance._state.adding or not instance.pk:
        instance._quota_previous_state = None
        return
    instance._quota_previous_state = sender.objects.filter(pk=instance.pk).values(
        "email",
        "quota_override_mode",
        "quota_override_bytes",
    ).first()


@receiver(post_save, sender=CustomUser)
def sync_effective_quota_after_save(
    sender,
    instance,
    created: bool,
    raw: bool,
    update_fields,
    **_kwargs,
) -> None:
    """Apply env policy and admin overrides after relevant user saves."""

    if raw:
        return

    if created:
        sync_user_quota(instance, refresh_usage=True)
        return

    should_sync = False
    if update_fields is not None:
        should_sync = bool(set(update_fields) & QUOTA_RELEVANT_FIELDS)
    else:
        previous = getattr(instance, "_quota_previous_state", None) or {}
        for field_name in QUOTA_RELEVANT_FIELDS:
            if previous.get(field_name) != getattr(instance, field_name, None):
                should_sync = True
                break

    if should_sync:
        sync_user_quota(instance, refresh_usage=True)
