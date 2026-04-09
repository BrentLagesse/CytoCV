"""Canonical channel-role helpers used across runtime, storage, and UI."""

from __future__ import annotations

CHANNEL_ROLE_DIC = "DIC"
CHANNEL_ROLE_BLUE = "channel_blue"
CHANNEL_ROLE_RED = "channel_red"
CHANNEL_ROLE_GREEN = "channel_green"

CHANNEL_ROLE_ORDER: tuple[str, ...] = (
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_RED,
    CHANNEL_ROLE_GREEN,
)

CHANNEL_ROLE_TO_DISPLAY: dict[str, str] = {
    CHANNEL_ROLE_DIC: "DIC",
    CHANNEL_ROLE_BLUE: "Blue",
    CHANNEL_ROLE_RED: "Red",
    CHANNEL_ROLE_GREEN: "Green",
}

CHANNEL_ROLE_TO_SLUG: dict[str, str] = {
    CHANNEL_ROLE_DIC: "dic",
    CHANNEL_ROLE_BLUE: "blue",
    CHANNEL_ROLE_RED: "red",
    CHANNEL_ROLE_GREEN: "green",
}

CHANNEL_SLUG_TO_ROLE: dict[str, str] = {
    slug: role for role, slug in CHANNEL_ROLE_TO_SLUG.items()
}

CHANNEL_DISPLAY_TO_ROLE: dict[str, str] = {
    label.lower(): role for role, label in CHANNEL_ROLE_TO_DISPLAY.items()
}

CHANNEL_NORMALIZATION_ALIASES: dict[str, str] = {
    "dic": CHANNEL_ROLE_DIC,
    "channel_blue": CHANNEL_ROLE_BLUE,
    "blue": CHANNEL_ROLE_BLUE,
    "dapi": CHANNEL_ROLE_BLUE,
    "hoechst": CHANNEL_ROLE_BLUE,
    "channel_red": CHANNEL_ROLE_RED,
    "red": CHANNEL_ROLE_RED,
    "mcherry": CHANNEL_ROLE_RED,
    "m-cherry": CHANNEL_ROLE_RED,
    "cherry": CHANNEL_ROLE_RED,
    "channel_green": CHANNEL_ROLE_GREEN,
    "green": CHANNEL_ROLE_GREEN,
    "gfp": CHANNEL_ROLE_GREEN,
}


def channel_sort_key(channel_role: str) -> int:
    """Return stable sort order for known channel roles."""

    try:
        return CHANNEL_ROLE_ORDER.index(channel_role)
    except ValueError:
        return len(CHANNEL_ROLE_ORDER)


def normalize_channel_role(value: object) -> str | None:
    """Normalize a legacy/new channel token into the canonical role key."""

    raw = str(value or "").strip()
    if not raw:
        return None
    if raw in CHANNEL_ROLE_ORDER:
        return raw

    lower = raw.lower()
    alias = CHANNEL_NORMALIZATION_ALIASES.get(lower) or CHANNEL_DISPLAY_TO_ROLE.get(lower)
    if alias:
        return alias

    compact = "".join(ch for ch in lower if ch.isalnum())
    if "dic" in compact or "brightfield" in compact or "transmission" in compact or compact == "bf":
        return CHANNEL_ROLE_DIC
    if "dapi" in compact or "hoechst" in compact:
        return CHANNEL_ROLE_BLUE
    if "mcherry" in compact or "cherry" in compact or compact.endswith("red"):
        return CHANNEL_ROLE_RED
    if "gfp" in compact or compact.endswith("green"):
        return CHANNEL_ROLE_GREEN
    return None


def channel_display_label(channel_role: object) -> str:
    """Return the user-facing label for a canonical role key."""

    normalized = normalize_channel_role(channel_role)
    if not normalized:
        return str(channel_role or "")
    return CHANNEL_ROLE_TO_DISPLAY[normalized]


def channel_slug(channel_role: object) -> str:
    """Return the public route slug for a canonical role key."""

    normalized = normalize_channel_role(channel_role)
    if not normalized:
        raise ValueError(f"Unknown channel role: {channel_role}")
    return CHANNEL_ROLE_TO_SLUG[normalized]


def channel_role_from_slug(slug: object) -> str | None:
    """Return the canonical role key for a public route slug."""

    return CHANNEL_SLUG_TO_ROLE.get(str(slug or "").strip().lower())


def channel_display_labels(channels: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    """Return display labels for a channel-role collection in stable order."""

    return [
        channel_display_label(channel)
        for channel in sorted(
            {
                normalized
                for normalized in (normalize_channel_role(channel) for channel in channels)
                if normalized
            },
            key=channel_sort_key,
        )
    ]
