from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from aegis.models import BlockedIP
from aegis.rate_limit import (
    _clean_streak_key,
    _violation_key,
    _window_slot,
    increment_violations,
    is_rate_limited,
    reset_if_clean_window,
)


@override_settings(AEGIS_RATE_LIMIT_REQUESTS=100)
class TestRateLimit(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_under_limit_passes(self) -> None:
        limited, count = is_rate_limited("127.0.0.14", 100, 60)
        assert not limited
        assert count == 1

    def test_over_limit_detected(self) -> None:
        ip = "127.0.0.3"
        window = 60
        max_req = 3
        for _ in range(max_req):
            is_rate_limited(ip, max_req, window)
        limited, count = is_rate_limited(ip, max_req, window)
        assert limited
        assert count == 4

    def test_window_slot_changes(self) -> None:
        slot_a = _window_slot(60)
        with patch("aegis.rate_limit.timezone") as mock_tz:
            mock_tz.now.return_value = timezone.now() + timedelta(seconds=120)
            mock_tz.timedelta = timedelta
            slot_b = _window_slot(60)
        assert slot_b > slot_a

    def test_violations_persist_without_clean_windows(self) -> None:
        ip = "127.0.0.99"
        window = 60
        threshold = 5
        base = _window_slot(window)
        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = base
            assert increment_violations(ip, window, threshold) == 1
            mock_slot.return_value = base + 2 * window
            assert increment_violations(ip, window, threshold) == 2
            mock_slot.return_value = base + 5 * window
            assert increment_violations(ip, window, threshold) == 3

    def test_one_violation_per_window(self) -> None:
        ip = "127.0.0.98"
        window = 60
        threshold = 5
        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = _window_slot(window)
            assert increment_violations(ip, window, threshold) == 1
            assert increment_violations(ip, window, threshold) == 1


@override_settings(AEGIS_RATE_LIMIT_REQUESTS=100)
class TestAutoBlock(TestCase):
    def test_under_limit_no_block(self) -> None:
        client = Client(REMOTE_ADDR="127.0.0.10")
        for _ in range(50):
            resp = client.get("/some-page/")
            assert resp.status_code in (200, 404)
        assert BlockedIP.objects.filter(ip="127.0.0.10").count() == 0

    def test_rate_limit_returns_429(self) -> None:
        ip = "127.0.0.11"
        client = Client(REMOTE_ADDR=ip)
        resp = None
        for _ in range(101):
            resp = client.get("/some-page/")
        assert resp is not None
        assert resp.status_code == 429
        assert "Retry-After" in resp

    def test_skip_paths_bypass_rate_limit(self) -> None:
        client = Client(REMOTE_ADDR="127.0.0.12")
        with patch.object(settings, "AEGIS_RATE_LIMIT_SKIP_PATHS", ["/skip-me/"]):
            resp = client.get("/skip-me/")
            assert resp.status_code != 429

    def test_auto_block_creates_blockedip(self) -> None:
        ip = "127.0.0.13"
        window = 60
        threshold = 3
        duration = 300

        from aegis.rate_limit import auto_block

        for _ in range(threshold):
            increment_violations(ip, window, threshold)

        auto_block(ip, duration)
        entry = BlockedIP.objects.filter(ip=ip).first()
        assert entry is not None
        assert entry.reason == "Rate limit violation threshold exceeded"
        assert entry.expires_at is not None
        assert entry.expires_at > timezone.now()

    def test_existing_blocked_ips_get_403_via_middleware(self) -> None:
        ip = "127.0.0.14"
        BlockedIP.objects.create(
            ip=ip,
            reason="auto-blocked",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        client = Client(REMOTE_ADDR=ip)
        resp = client.get("/some-page/")
        assert resp.status_code == 403

    def test_permanent_block_returns_403(self) -> None:
        ip = "127.0.0.4"
        BlockedIP.objects.create(ip=ip, reason="permanent", expires_at=None)
        client = Client(REMOTE_ADDR=ip)
        resp = client.get("/some-page")
        assert resp.status_code == 403


class TestCleanWindowReset(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_reset_after_n_consecutive_clean_windows(self) -> None:
        ip = "127.0.0.50"
        window = 60
        threshold = 3
        base = _window_slot(window)
        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = base
            increment_violations(ip, window, threshold)
            mock_slot.return_value = base + window
            increment_violations(ip, window, threshold)
            assert cache.get(_violation_key(ip)) == 2

            mock_slot.return_value = base + 2 * window
            reset_if_clean_window(ip, window, threshold)
            mock_slot.return_value = base + 3 * window
            reset_if_clean_window(ip, window, threshold)
            mock_slot.return_value = base + 4 * window
            result = reset_if_clean_window(ip, window, threshold)
            assert result == 0
            assert cache.get(_violation_key(ip)) in (0, None)

    def test_violation_breaks_clean_streak(self) -> None:
        ip = "127.0.0.51"
        window = 60
        threshold = 3
        base = _window_slot(window)
        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = base
            increment_violations(ip, window, threshold)
            mock_slot.return_value = base + window
            reset_if_clean_window(ip, window, threshold)
            mock_slot.return_value = base + 2 * window
            reset_if_clean_window(ip, window, threshold)
            mock_slot.return_value = base + 3 * window
            increment_violations(ip, window, threshold)
            assert cache.get(_clean_streak_key(ip)) == 0

    def test_no_op_on_ip_with_no_violation_history(self) -> None:
        ip = "127.0.0.60"
        window = 60
        threshold = 3
        result = reset_if_clean_window(ip, window, threshold)
        assert result == 0
        assert cache.get(_clean_streak_key(ip)) is None

    def test_duplicate_clean_calls_same_window_are_noop(self) -> None:
        ip = "127.0.0.61"
        window = 60
        threshold = 3
        base = _window_slot(window)
        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = base
            increment_violations(ip, window, threshold)
            mock_slot.return_value = base + window
            r1 = reset_if_clean_window(ip, window, threshold)
            r2 = reset_if_clean_window(ip, window, threshold)
            assert r1 == r2
            assert cache.get(_clean_streak_key(ip)) == 1
