import datetime
from datetime import timezone

from django.db import models
from django.db.models import (
    DateTimeField,
    GenericIPAddressField,
    IntegerField,
    TextField,
)
from django.utils import timezone as utils_timezone
from .apps import AegisConfig

class BlockedIP(models.Model):
    ip = GenericIPAddressField(
        primary_key=True, db_index=True, verbose_name="IP  address"
    )
    reason = TextField()
    datetime_added = DateTimeField(default=utils_timezone.now, db_index=True)
    cooldown = IntegerField(default=AegisConfig.defaults["cooldown"],help_text="Cooldown period")
    last_seen = DateTimeField(blank=True, null=True, db_index=True)
    tally = IntegerField(default=0, help_text="No of times this ip has been blocked")

    class Meta:
        get_latest_by = "datetime_added"
        verbose_name = "blocked IP"
        verbose_name_plural = "blocked IPs"
        ordering = ["-last_seen", "-datetime_added", "ip"]

    def __str__(self) -> str:
        return f"{self.ip}"

    def has_expired(self):
        quiet_time = datetime.datetime.now(timezone.utc)-(self.last_seen or self.datetime_added)
        return quiet_time.days >= self.cooldown

class RateLimit(models.Model):
   pass