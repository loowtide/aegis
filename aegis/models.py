from datetime import datetime
from enum import IntFlag
from django.db import models
from django.db.models import (
    DateTimeField,
    GenericIPAddressField,
    PositiveIntegerField,
    TextField,
    FloatField,
)
from django.db import transaction
from django.utils import timezone as utils_timezone
from .apps import AegisConfig

class HttpMethod(IntFlag):
    NONE=0
    GET=1<<0
    HEAD=1<<1
    POST=1<<2
    PUT=1<<3
    DELETE=1<<4
    CONNECT=1<<5
    OPTIONS=1<<6
    TRACE=1<<7
    PATCH=1<<8


class BlockedIP(models.Model):
    ip = GenericIPAddressField(
        primary_key=True, db_index=True, verbose_name="IP  address"
    )
    reason = TextField()
    datetime_added = DateTimeField(default=utils_timezone.now, db_index=True)
    cooldown = PositiveIntegerField(
        default=AegisConfig.defaults["cooldown"], help_text="Cooldown period"
    )
    last_seen = DateTimeField(blank=True, null=True, db_index=True)
    tally = PositiveIntegerField(default=0, help_text="No of times this ip has been blocked")

    class Meta:
        get_latest_by = "datetime_added"
        verbose_name = "blocked IP"
        verbose_name_plural = "blocked IPs"
        ordering = ["-last_seen", "-datetime_added", "ip"]

    def __str__(self) -> str:
        return f"{self.ip}"

    def has_expired(self):
        quiet_time = utils_timezone.now() - (self.last_seen or self.datetime_added)
        return quiet_time.total_seconds() >= self.cooldown

class RateLimit(models.Model):
    ip=GenericIPAddressField(db_index=True,verbose_name="IP address")
    method_mask=PositiveIntegerField(default=HttpMethod.GET,db_index=True)
    bucket_level=FloatField(default=10.0)
    last_updated=DateTimeField(auto_now=True)
    max_capacity=FloatField(default=AegisConfig.RateLimitDefaults["CAPACITY"],help_text="Max bucket capacity")
    refill_rate=FloatField(default=AegisConfig.RateLimitDefaults["REFILL_RATE"])
    expiration_days=PositiveIntegerField(default=AegisConfig.RateLimitDefaults["EXPIRATION_DAYS"],help_text="Rate limit expiration date")

    class Meta:
        unique_together=('ip','method_mask')

    def __str__(self) -> str:
        return f"{self.ip} - {self.bucket_level}/{self.max_capacity}"

    def consume(self)->bool:
        with transaction.atomic():
            obj=RateLimit.objects.select_for_update().get(pk=self.pk)
            now:datetime=utils_timezone.now()
            delta_time=(now-obj.last_updated).total_seconds()
            added_tokens=delta_time*obj.refill_rate
            new_level=min(obj.max_capacity,obj.bucket_level+added_tokens)

            if new_level>=1.0:
                obj.bucket_level=new_level-1.0
                obj.save(update_fields=['bucket_level','last_visited'])
                return True
            obj.bucket_level=new_level
            obj.save(update_fields=['bucket_level','last_updated'])
            return False

