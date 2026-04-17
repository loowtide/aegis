from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import BlockedIP, BlockedIPAdminForm, HttpMethod, RateLimit, RateLimitRule


def allowed_method_toggle(method: HttpMethod):
    def toggle_method(modeladmin, request, queryset):
        if hasattr(queryset.model, "allowed_methods"):
            field_name = "allowed_methods"
        else:
            messages.error(request, f"model {queryset.model} does not support toggling")
            return
        for entry in queryset:
            val = getattr(entry, field_name, 0)
            setattr(entry, field_name, val ^ method.value)
            entry.save()
        messages.success(
            request, f"Toggled {method.name} for {queryset.count()}  enteries"
        )

    toggle_method.__name__ = f"toggle {method.name}"
    toggle_method.short_description = f"Toggle {method.name} Permission"
    return toggle_method


method_actions = [allowed_method_toggle(m) for m in HttpMethod if m.value > 0]


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    form = BlockedIPAdminForm
    exclude = ["allowed_methods"]
    list_display = (
        "ip",
        "is_active",
        "time_remaining",
        "tally",
        "allowed_methods_str",
        "last_seen",
    )
    list_filter = ("datetime_added", "cooldown")
    search_fields = ("ip", "reason")
    readonly_fields = ["datetime_added"]

    class Meta:
        model = BlockedIP

    @admin.display(description="Active", boolean=True)
    def is_active(self, obj: BlockedIP):
        return not obj.has_expired()

    @admin.display(description="Days Remaining")
    def time_remaining(self, obj: BlockedIP):
        reference_time = obj.last_seen or obj.datetime_added
        elapsed = timezone.now() - reference_time
        remaining_days = obj.cooldown - elapsed.days

        if remaining_days <= 0:
            return format_html('<span style="color:grey;">Expired</span>')
        return f"{remaining_days} days"

    @admin.display(description="Short Reason")
    def short_reason(self, obj: BlockedIP):
        return (obj.reason[:30] + "...") if len(obj.reason) > 30 else obj.reason

    actions = ["reset_ips"] + method_actions

    @admin.action(description="Reset selected IPs")
    def reset_ips(self, request, queryset):
        count = queryset.update(tally=0, last_seen=None)
        self.message_user(
            request, f"Successfully reset stats for {count} IPs", messages.SUCCESS
        )


class RateLimitRuleInline(admin.TabularInline):
    model = RateLimitRule
    extra = 1
    fields = ("method", "max_capacity", "refill_rate", "bucket_level", "last_updated")
    readonly_fields = ("last_updated",)


@admin.register(RateLimit)
class RateLimitAdmin(admin.ModelAdmin):
    inlines = [RateLimitRuleInline]
    list_display = (
        "ip",
        "get_methods",
    )
    list_filter = ("rules__method", "rules__last_updated")
    search_fields = ("ip",)

    class Meta:
        model = RateLimit

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("rules")

    @admin.display(description="Methods")
    def get_methods(self, obj):
        if not obj.pk:
            return "---"
        rules = obj.rules.all()
        if not rules:
            return "No rules set"
        lines = [
            f"{r.get_method_display()}: Cap {r.max_capacity} (Refill {r.refill_rate}/s)"
            for r in rules
        ]
        return ", ".join(lines)
