"""Login rate limiting utilities."""
from __future__ import annotations

import time
from dataclasses import dataclass

from django.core.cache import cache


@dataclass(frozen=True)
class RateLimitState:
    limited: bool
    retry_after_seconds: int
    reset_at_epoch: float
    attempts: int


def _cache_key(ip_address: str) -> str:
    return f"login_rate_limit:{ip_address}"


def _prune_attempts(attempts: list[float], now: float, window_seconds: int) -> list[float]:
    if not attempts:
        return []
    cutoff = now - window_seconds
    return [timestamp for timestamp in attempts if timestamp >= cutoff]


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def get_rate_limit_state(request, window_seconds: int, max_attempts: int) -> RateLimitState:
    ip_address = get_client_ip(request)
    now = time.time()
    key = _cache_key(ip_address)
    attempts: list[float] = cache.get(key, [])
    attempts = _prune_attempts(attempts, now, window_seconds)
    if attempts:
        cache.set(key, attempts, timeout=window_seconds)
    limited = len(attempts) >= max_attempts
    retry_after = 0
    reset_at = now
    if limited:
        oldest = attempts[0]
        retry_after = max(0, int(window_seconds - (now - oldest)))
        reset_at = now + retry_after
    return RateLimitState(limited, retry_after, reset_at, len(attempts))


def record_failed_attempt(request, window_seconds: int, max_attempts: int) -> RateLimitState:
    ip_address = get_client_ip(request)
    now = time.time()
    key = _cache_key(ip_address)
    attempts: list[float] = cache.get(key, [])
    attempts = _prune_attempts(attempts, now, window_seconds)
    attempts.append(now)
    cache.set(key, attempts, timeout=window_seconds)
    limited = len(attempts) >= max_attempts
    retry_after = 0
    reset_at = now
    if limited:
        oldest = attempts[0]
        retry_after = max(0, int(window_seconds - (now - oldest)))
        reset_at = now + retry_after
    return RateLimitState(limited, retry_after, reset_at, len(attempts))


def clear_attempts(request) -> None:
    ip_address = get_client_ip(request)
    cache.delete(_cache_key(ip_address))
