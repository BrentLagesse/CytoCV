"""Shared wavelength channel-order helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_ORDER,
    CHANNEL_ROLE_RED,
    normalize_channel_role,
)

DEFAULT_FALLBACK_CHANNEL_ORDER: tuple[str, ...] = (
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
)


def normalize_channel_order(
    value: Iterable[Any] | None,
    *,
    default: Iterable[str] = DEFAULT_FALLBACK_CHANNEL_ORDER,
) -> list[str]:
    """Return a complete canonical channel-role order, or the default order."""

    default_order = list(default)
    if value is None or isinstance(value, (str, bytes)):
        return default_order

    normalized: list[str] = []
    for item in value:
        channel = normalize_channel_role(item)
        if channel is None:
            return default_order
        normalized.append(channel)

    if len(normalized) != len(CHANNEL_ROLE_ORDER):
        return default_order
    if set(normalized) != set(CHANNEL_ROLE_ORDER):
        return default_order
    return normalized


def validate_channel_order(value: Iterable[Any] | None) -> list[str] | None:
    """Return a complete canonical channel order, or None when invalid."""

    normalized = normalize_channel_order(value, default=())
    if len(normalized) != len(CHANNEL_ROLE_ORDER):
        return None
    return normalized


def channel_order_to_config(order: Iterable[Any] | None) -> dict[str, int]:
    """Convert image-plane channel order to a channel role -> plane index map."""

    normalized_order = validate_channel_order(order)
    if normalized_order is None:
        normalized_order = list(DEFAULT_FALLBACK_CHANNEL_ORDER)
    return {channel: index for index, channel in enumerate(normalized_order)}


def fallback_channel_config(order: Iterable[Any] | None = None) -> dict[str, int]:
    """Return the configured complete fallback channel mapping."""

    return channel_order_to_config(
        normalize_channel_order(order, default=DEFAULT_FALLBACK_CHANNEL_ORDER)
    )


def resolve_channel_config(
    metadata_config: dict[str, int] | None,
    *,
    prefer_metadata: bool = True,
    fallback_order: Iterable[Any] | None = None,
) -> dict[str, int]:
    """Resolve metadata-derived channel config with a configurable fallback."""

    if prefer_metadata and metadata_config:
        return dict(metadata_config)
    return fallback_channel_config(fallback_order)
