import time
from django.core.cache import cache


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def build_rate_limit_keys(ip: str, username: str) -> list[str]:
    keys = [f"rl:login:ip:{ip}"]
    if username:
        keys.append(f"rl:login:user:{username.lower()}")
        keys.append(f"rl:login:ip_user:{ip}:{username.lower()}")
    return keys


def _ttl(window_seconds: int, lockout_schedule: list[int] | None = None) -> int:
    if lockout_schedule:
        return max(max(lockout_schedule), window_seconds, 60)
    return max(window_seconds, 60)


def _prune_attempts(attempts: list[int], now: int, window_seconds: int) -> list[int]:
    return [ts for ts in attempts if now - ts < window_seconds]


def _get_state(key: str, now: int, window_seconds: int, mode: str) -> dict:
    state = cache.get(key) or {}
    if mode == "sliding":
        attempts = state.get("attempts", [])
        if not isinstance(attempts, list):
            attempts = []
        state["attempts"] = _prune_attempts(attempts, now, window_seconds)
        return state

    last_attempt = int(state.get("last_attempt", 0))
    locked_until = int(state.get("locked_until", 0))

    if locked_until and locked_until <= now:
        locked_until = 0
        state["locked_until"] = 0
        state["count"] = 0

    if last_attempt and now - last_attempt > window_seconds:
        state["count"] = 0

    state.setdefault("count", 0)
    state.setdefault("level", 0)
    state.setdefault("locked_until", locked_until)
    state.setdefault("last_attempt", last_attempt)
    return state


def check_rate_limit(
    keys: list[str],
    max_attempts: int,
    window_seconds: int,
    lockout_schedule: list[int],
    mode: str = "sliding",
) -> tuple[bool, int, int]:
    now = int(time.time())
    retry_after = 0
    limited = False
    level = 0
    for key in keys:
        state = _get_state(key, now, window_seconds, mode)
        if mode == "sliding":
            attempts = state.get("attempts", [])
            if len(attempts) >= max_attempts:
                limited = True
                oldest = attempts[0]
                retry_after = max(retry_after, max(0, oldest + window_seconds - now))
            cache.set(key, state, timeout=_ttl(window_seconds))
            continue

        locked_until = int(state.get("locked_until", 0))
        if locked_until > now:
            limited = True
            retry_after = max(retry_after, locked_until - now)
            level = max(level, int(state.get("level", 0)))
    return limited, retry_after, level


def register_failure(
    keys: list[str],
    max_attempts: int,
    window_seconds: int,
    lockout_schedule: list[int],
    mode: str = "sliding",
) -> None:
    now = int(time.time())
    for key in keys:
        state = _get_state(key, now, window_seconds, mode)
        if mode == "sliding":
            attempts = state.get("attempts", [])
            if len(attempts) < max_attempts:
                attempts.append(now)
            state["attempts"] = attempts
            cache.set(key, state, timeout=_ttl(window_seconds))
            continue

        if state.get("locked_until", 0) > now:
            continue

        state["count"] = int(state.get("count", 0)) + 1
        state["last_attempt"] = now

        if state["count"] >= max_attempts:
            level = int(state.get("level", 0))
            if lockout_schedule:
                idx = min(level, len(lockout_schedule) - 1)
                lock_seconds = lockout_schedule[idx]
            else:
                lock_seconds = window_seconds
            state["locked_until"] = now + lock_seconds
            state["count"] = 0
            state["level"] = min(level + 1, max(len(lockout_schedule) - 1, 0))

        cache.set(key, state, timeout=_ttl(window_seconds, lockout_schedule))


def reset_limits(keys: list[str]) -> None:
    for key in keys:
        cache.delete(key)
