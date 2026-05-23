import logging
from datetime import datetime, timedelta
from enum import IntFlag

from django import forms
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import (
    DateTimeField,
    FloatField,
    GenericIPAddressField,
    PositiveIntegerField,
    TextField,
)
from django.utils import timezone as utils_timezone

from .apps import AegisConfig

logger = logging.getLogger(__name__)


class HttpMethod(IntFlag):
    NONE = 0
    GET = 1 << 0
    HEAD = 1 << 1
    POST = 1 << 2
    PUT = 1 << 3
    DELETE = 1 << 4
    CONNECT = 1 << 5
    OPTIONS = 1 << 6
    TRACE = 1 << 7
    PATCH = 1 << 8


class BlockedIP(models.Model):
    ip = GenericIPAddressField(primary_key=True, verbose_name="IP address")
    allowed_methods = PositiveIntegerField(
        default=0, help_text="HTTP methods this IP can use"
    )
    reason = TextField()
    datetime_added = DateTimeField(default=utils_timezone.now, db_index=True)
    cooldown = PositiveIntegerField(
        default=AegisConfig.defaults["cooldown"], help_text="Cooldown period"
    )
    last_seen = DateTimeField(blank=True, null=True, db_index=True)
    tally = PositiveIntegerField(
        default=0, help_text="No of times this ip has been blocked"
    )

    class Meta:
        get_latest_by = "datetime_added"
        verbose_name = "blocked IP"
        verbose_name_plural = "blocked IPs"
        ordering = ["-last_seen", "-datetime_added", "ip"]

    def __str__(self) -> str:
        return f"{self.ip}"

    def has_expired(self):
        quiet_time = (self.last_seen or self.datetime_added) + timedelta(
            days=self.cooldown
        )
        return utils_timezone.now() >= quiet_time

    def allowed_methods_str(self):
        return BlockedIP.intflags_to_names(self.allowed_methods)

    @classmethod
    def methods_to_intflags(cls, raw_methods: str) -> int:
        flag = 0
        for s in raw_methods.split(","):
            method = getattr(HttpMethod, s.strip().upper(), None)
            if method is None:
                logger.error(f"Can't convert the HTTP method '{s.strip()}' ,skipping")
            else:
                flag |= method.value
        return flag

    @classmethod
    def intflags_to_names(cls, flag: int):
        return ",".join(
            method.name
            for method in HttpMethod
            if method.value > 0 and method.name and flag & method
        )


class AegisMethodForm(forms.ModelForm):
    method_selection = forms.MultipleChoiceField(
        choices=[(m.name, m.name) for m in HttpMethod if m.value > 0],
        required=False,
        label="Allowed HTTP methods",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        val = getattr(self.instance, "allowed_methods", None)
        if val is None:
            val = getattr(self.instance, "method_mask", 0)
        if val:
            self.initial["method_selection"] = [
                m.name for m in HttpMethod if m.value > 0 and (val & m.value)
            ]

    def save(self, commit=True):
        selected = self.cleaned_data.get("method_selection", [])
        flag_value = BlockedIP.methods_to_intflags(",".join(selected))
        if hasattr(self.instance, "allowed_methods"):
            self.instance.allowed_methods = flag_value
        else:
            self.instance.method_mask = flag_value
        return super().save(commit=commit)


class GlobalRateLimitRule(models.Model):
    """
    Global rate limit rules for http methods
    """

    method = PositiveIntegerField(
        choices=[(m.value, m.name) for m in HttpMethod if m.value > 0],
        unique=True,
        verbose_name="HTTP Method defaults",
    )
    max_capacity = FloatField(default=10.0)
    bucket_level = FloatField(default=10.0)
    refill_rate = FloatField(default=1.0)

    def clean(self):
        if self.bucket_level > self.max_capacity:
            raise ValidationError("bucket_level cannot exceeds max_capacity")


class RateLimitRule(models.Model):
    """
    Rate limit rules for a specific ip
    """

    ip = GenericIPAddressField(db_index=True, unique=True, verbose_name="IP address")
    method = PositiveIntegerField(
        choices=[(m.value, m.name) for m in HttpMethod if m.value > 0]
    )
    max_capacity = FloatField(default=10.0)
    bucket_level = FloatField(default=10.0)
    refill_rate = FloatField(default=1.0)
    last_updated = DateTimeField(default=utils_timezone.now)

    class Meta:
        unique_together = ("ip", "method")

    @classmethod
    def consume(cls, ip: str, method: int) -> bool:
        with transaction.atomic():
            rule = (
                cls.objects.select_for_update().filter(ip=ip, method=method)
            ).first()
            if rule is None:
                try:
                    g = GlobalRateLimitRule.objects.get(method=method)
                except GlobalRateLimitRule.DoesNotExist:
                    return True
                with transaction.atomic():
                    rule, _ = cls.objects.get_or_create(
                        ip=ip,
                        method=method,
                        defaults={
                            "max_capacity": g.max_capacity,
                            "bucket_level": g.bucket_level,
                            "refill_rate": g.refill_rate,
                            "last_updated": utils_timezone.now(),
                        },
                    )
                rule = cls.objects.select_for_update().get(pk=rule.pk)
            now: datetime = utils_timezone.now()
            delta_time = (now - rule.last_updated).total_seconds()
            if delta_time < 0:
                delta_time = 0
            added_tokens = delta_time * rule.refill_rate
            new_level = min(rule.max_capacity, rule.bucket_level + added_tokens)
            allowed = new_level >= 1.0
            if allowed:
                new_level -= 1.0
            rule.bucket_level = new_level
            rule.last_updated = now
            rule.save(update_fields=["bucket_level", "last_updated"])
            return allowed


class BlockedIPAdminForm(AegisMethodForm):
    class Meta:
        model = BlockedIP
        fields = "__all__"
