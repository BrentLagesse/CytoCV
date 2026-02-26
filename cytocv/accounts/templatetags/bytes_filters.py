"""Template filters for formatting byte sizes."""

from __future__ import annotations

from django import template

register = template.Library()

@register.filter(name="filesize")
def filesize(value: float) -> str:
    """Convert a byte count to a human-readable size string.

    Args:
        value: Size in bytes.

    Returns:
        Human-readable size string (e.g., "1.50 MB").
    """
    units = ["bytes", "KB", "MB", "GB", "TB"]

    if value == 0:
        return "0 bytes"
    i = 0
    while value >= 1024 and i < len(units) - 1:
        value /= 1024.0
        i += 1
    return f"{value:.2f} {units[i]}"
