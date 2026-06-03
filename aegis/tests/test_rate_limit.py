from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from aegis.models import BlockedIP
from aegis.rate_limit import (
    _window_slot,
    increment_violations,
    is_rate_limited,
    reset_if_clean_window,
)


class TestRateLimit:
    def test_under_limit_passes(self) -> None:
        limited, count = is_rate_limited("127.0.0.1", 100, 60)
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

    def test_violations_reset_on_clean_window(self) -> None:
        ip = "127.0.0.99"
        window = 60
        threshold = 5
        v1 = increment_violations(ip, window, threshold)
        assert v1 == 1
        v2 = increment_violations(ip, window, threshold)
        assert v2 == 2

        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = _window_slot(window) + window
            r = reset_if_clean_window(ip, window, threshold)
            assert r == 0

    def test_violations_persist_within_same_window(self) -> None:
        ip = "127.0.0.98"
        window = 60
        threshold = 5
        increment_violations(ip, window, threshold)
        increment_violations(ip, window, threshold)
        with patch("aegis.rate_limit._window_slot") as mock_slot:
            mock_slot.return_value = _window_slot(window)
            r = reset_if_clean_window(ip, window, threshold)
            assert r == 2


class TestAutoBlock:
    @pytest.mark.django_db
    def test_under_limit_no_block(self) -> None:
        client = Client(REMOTE_ADDR="127.0.0.10")
        for _ in range(50):
            resp = client.get("/some-page/")
            assert resp.status_code in (200, 404)
        assert BlockedIP.objects.filter(ip="127.0.0.10").count() == 0

    @pytest.mark.django_db
    def test_rate_limit_returns_429(self) -> None:
        ip = "127.0.0.11"
        client = Client(REMOTE_ADDR=ip)
        resp = None
        for _ in range(101):
            resp = client.get("/some-page/")
        assert resp is not None
        assert resp.status_code == 429
        assert "Retry-After" in resp

    @pytest.mark.django_db
    def test_skip_paths_bypass_rate_limit(self) -> None:
        client = Client(REMOTE_ADDR="127.0.0.12")
        with patch.object(settings, "AEGIS_RATE_LIMIT_SKIP_PATHS", ["/skip-me/"]):
            resp = client.get("/skip-me/")
            assert resp.status_code != 429

    @pytest.mark.django_db
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

    @pytest.mark.django_db
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
