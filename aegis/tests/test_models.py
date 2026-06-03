from datetime import timedelta

import pytest
from django.utils import timezone

from aegis.models import BlockedIP


@pytest.mark.django_db
class TestBlockedIP:
    def test_is_active_when_expires_at_is_none(self) -> None:
        """Permanent Blocks are always active."""

        blocked = BlockedIP.objects.create(
            ip="127.0.0.3",
            reason="spam",
        )
        assert blocked.is_active

    def test_is_active_when_expires_at_in_future(self) -> None:
        """BLocks with future expiry are still active."""

        future = timezone.now() + timedelta(hours=1)
        blocked = BlockedIP.objects.create(ip="127.0.0.2", expires_at=future)
        assert blocked.is_active

    def test_is_active_expires_at_in_past(self) -> None:
        """Blocks past their expiry are not active(expired)."""

        past = timezone.now() - timedelta(hours=1)
        blocked = BlockedIP.objects.create(ip="127.0.0.3", expires_at=past)
        assert not blocked.is_active
