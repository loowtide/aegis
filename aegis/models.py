from django.db import models
from django.db.models import (
    DateTimeField,
    GenericIPAddressField,
    IntegerField,
    TextField,
)


class BlockedIP(models.Model):
    ip = GenericIPAddressField(unique=True, db_index=True)
    reason = TextField()
    datetime_added = DateTimeField(auto_now_add=True)
    cooldown = DateTimeField(blank=True, null=True)
    last_seen = DateTimeField(blank=True, null=True, db_index=True)
    count = IntegerField(default=0, help_text="No of times this ip has been blocked")

    class Meta:
        verbose_name = "blocked IP"
        verbose_name_plural = "blocked IPs"
        ordering = ["ip", "created_at"]
