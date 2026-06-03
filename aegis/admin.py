from __future__ import annotations

from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.utils import timezone

from aegis.models import BlockedIP


class ActiveStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[BlockedIP]
    ) -> list[tuple[str, str]]:
        return [
            ("active", "Active"),
            ("expired", "Expired"),
            ("permanent", "Permanent"),
        ]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[BlockedIP]
    ) -> QuerySet[BlockedIP]:
        now = timezone.now()
        if self.value() == "active":
            return queryset.filter(expires_at__gt=now)
        if self.value() == "blocked":
            return queryset.filter(expires_at__lte=now)
        if self.value() == "permanent":
            return queryset.filter(expires_at__isnull=True)
        return queryset


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["ip", "reason", "blocked_at", "expires_at", "last_seen"]
    search_fields = [
        "ip",
    ]
    list_filter = [ActiveStatusFilter, "blocked_at"]
    ordering = ["-blocked_at"]
