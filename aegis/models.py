from django.db import models
from django.utils import timezone


class BlockedIP(models.Model):
    ip = models.GenericIPAddressField(
        unique=True, db_index=True, verbose_name="IP address"
    )
    reason = models.TextField()
    blocked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    tally = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Blocked IP"
        ordering = ["-blocked_at"]

    def __str__(self):
        return f"{self.ip}"

    @property
    def is_active(self) -> bool:
        if self.expires_at is None:
            return True  # permanent block
        return timezone.now() < self.expires_at
