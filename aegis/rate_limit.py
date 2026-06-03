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


def _last_violation_window_key(ip: str) -> str:
    return f"aegis:{ip}:last_violated_window"


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
    if cache.get(_last_violation_window_key(ip)) == slot:
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
    cache.set(_last_violation_window_key(ip), slot, timeout=timeout)
    return v


"""
def reset_if_clean_window(ip: str, window: int, threshold: int) -> int:
    key = _violation_key(ip)
    last_slot = cache.get(_last_violation_window_key(ip))
    if last_slot is None:
        return 0
    current_slot = _window_slot(window)
    if current_slot > last_slot:
        timeout = window * threshold * 2
        cache.set(key, 0, timeout=timeout)
        return 0
    return cache.get(key) or 0
"""


def auto_block(ip: str, duration: int) -> BlockedIP:
    reason = "Rate limit violation threshold exceeded"
    expires_at = timezone.now() + timedelta(seconds=duration)
    blocked, _ = BlockedIP.objects.get_or_create(
        ip=ip,
        defaults={"reason": reason, "expires_at": expires_at},
    )
    if not blocked.expires_at or blocked.expires_at < timezone.now():
        blocked.expires_at = expires_at
        blocked.reason = reason
        blocked.save(update_fields=["expires_at", "reason"])
    return blocked
