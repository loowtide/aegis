from django.contrib import admin,messages
from django.http import HttpRequest
from .models import BlockedIP, HttpMethod, RateLimit
from django.utils import timezone
from django.utils.html import format_html

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display=(
        'ip','is_active','time_remaining','tally','reason','last_seen'
    )
    list_filter=('datetime_added','cooldown')
    search_fields=('ip','reason')
    readonly_fields=['datetime_added']

    @admin.display(description="Active",boolean=True)
    def is_active(self,obj:BlockedIP):
        return not obj.has_expired()

    @admin.display(description="Days Remaining")
    def time_remaining(self,obj:BlockedIP):
        reference_time=obj.last_seen or obj.datetime_added
        elapsed=timezone.now()-reference_time
        remaining_days=obj.cooldown-elapsed.days

        if remaining_days<=0:
            return format_html('<span style="color:grey;">Expired</span>')
        return f"{remaining_days} days"

    @admin.display(description="Short Reason")
    def short_reason(self,obj:BlockedIP):
        return (obj.reason[:30]+'...') if len(obj.reason)>30 else obj.reason

    actions=['reset_ips']

    @admin.action(description="Reset selected IPs")
    def reset_ips(self,request,queryset):
        tally=queryset.update(tally=0,last_seen=None)
        self.message_user(request,f"Successfully reset stats for {tally} IPs",messages.SUCCESS)



