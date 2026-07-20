from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from aegis.models import BlockedIP


def _window_slot(window: int) -> int:
    now = int(timezone.now().timestamp())
    return now - (now % window)


def _rate_limit_key(ip: str, window: int) -> str:
    slot = _window_slot(window)
    return f"aegis:{ip}:{slot}"


def _violation_key(ip: str) -> str:
    return f"aegis:{ip}:violations"


def _clean_streak_key(ip: str) -> str:
    return f"aegis:{ip}:clean_streak"


def _last_seen_window_key(ip: str) -> str:
    return f"aegis:{ip}:last_seen_window"


def is_rate_limited(
    ip: str, max_requests: int = 100, window: int = 60
) -> tuple[bool, int]:
    key = _rate_limit_key(ip, window)
    if cache.add(key, 1, timeout=window * 2):
        return False, 1
    try:
        count = cache.incr(key)
    except ValueError:
        cache.add(key, 1, timeout=window * 2)
        count = 1
    return count > max_requests, count


def get_violations(ip: str) -> int:
    return cache.get(_violation_key(ip)) or 0


def increment_violations(ip: str, window: int, threshold: int) -> int:
    key = _violation_key(ip)
    timeout = window * threshold * 2
    slot = _window_slot(window)
    last_key = _last_seen_window_key(ip)
    if cache.get(last_key) == slot:
        return get_violations(ip)
    if cache.add(key, 1, timeout=timeout):
        v = 1
    else:
        try:
            v = cache.incr(key)
        except ValueError:
            cache.add(key, 1, timeout=timeout)
            v = 1
    cache.touch(key, timeout)
    cache.set(_clean_streak_key(ip), 0, timeout=timeout)
    cache.set(last_key, slot, timeout=timeout)
    return v


def reset_if_clean_window(ip: str, window: int, threshold: int) -> int:
    key = _violation_key(ip)
    streak = _clean_streak_key(ip)
    last_key = _last_seen_window_key(ip)
    timeout = window * threshold * 2
    slot = _window_slot(window)
    if cache.get(last_key) == slot:
        return get_violations(ip)

    cache.set(last_key, slot, timeout=timeout)
    if get_violations(ip) == 0:
        return 0
    if cache.add(streak, 1, timeout=timeout):
        streak_cnt = 1
    else:
        try:
            streak_cnt = cache.incr(streak)
        except ValueError:
            cache.add(streak, 1, timeout=timeout)
            streak_cnt = 1
    cache.touch(streak, timeout)

    if streak_cnt >= threshold:
        cache.set(key, 0, timeout=timeout)
        cache.set(streak, 0, timeout=timeout)
        return 0

    return get_violations(ip)


def auto_block(ip: str, duration: int, extend_active: bool = False) -> BlockedIP:
    reason = "Rate limit violation threshold exceeded"
    expires_at = timezone.now() + timedelta(seconds=duration)
    blocked, _ = BlockedIP.objects.get_or_create(
        ip=ip,
        defaults={"reason": reason, "expires_at": expires_at},
    )
    if not blocked.expires_at or blocked.expires_at < timezone.now() or extend_active:
        blocked.expires_at = expires_at
        blocked.reason = reason
        blocked.save(update_fields=["expires_at", "reason"])
    return blocked
