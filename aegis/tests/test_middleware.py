from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from aegis.models import BlockedIP


@pytest.mark.django_db
class TestMiddleware:
    def test_middleware_returns_403_for_blocked_ip(self) -> None:
        """Middleware returns 403 for blocked ip."""

        future = timezone.now() + timedelta(hours=1)
        BlockedIP.objects.create(ip="127.0.0.1", reason="test", expires_at=future)
        client = Client(REMOTE_ADDR="127.0.0.1")
        response = client.get("/admin/")
        assert response.status_code == 403

    def test_middlware_passes_through_non_block(self) -> None:
        """Middleware let pass the non blocked ips."""

        client = Client(REMOTE_ADDR="127.0.0.1")
        response = client.get("/admin/")
        assert response.status_code == 302

    def test_middleware_passes_through_expired_ips(self) -> None:
        """Middleware also let expired ips to pass through."""

        past = timezone.now() - timedelta(hours=1)
        BlockedIP.objects.create(ip="127.0.0.1", expires_at=past)
        client = Client(REMOTE_ADDR="127.0.0.1")
        response = client.get("/admin/")
        assert response.status_code == 302

    def test_middleware_tally_increment(self) -> None:
        """Tally increments on blocked ips"""

        future = timezone.now() + timedelta(hours=1)
        blocked = BlockedIP.objects.create(ip="127.0.0.1", expires_at=future)
        client = Client(REMOTE_ADDR="127.0.0.1")
        for i in range(4):
            client.get("/admin/")
        blocked.refresh_from_db()
        assert blocked.tally == 4
