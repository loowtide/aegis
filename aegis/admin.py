from django.contrib import admin
from django.utils import timezone

from aegis.models import BlockedIP


class ActiveStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("active", "Active"),
            ("expired", "Expired"),
            ("permanent", "Permanent"),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "active":
            return queryset.filter(expires_at__gt=now)
        if self.value() == "blocked":
            return queryset.filter(expires_at__lte=now)
        if self.value() == "permanent":
            return queryset.filter(expires_at__isnull=True)
        return queryset


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ["ip", "reason", "blocked_at", "expires_at", "last_seen"]
    search_fields = [
        "ip",
    ]
    list_filter = [ActiveStatusFilter, "blocked_at"]
    ordering = ["-blocked_at"]
