"""Exception types used across analysis pipeline services."""

from __future__ import annotations


class AnalysisCancelled(Exception):
    """Raised when a running analysis batch is cancelled."""
