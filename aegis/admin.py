from itertools import count

from django.contrib import admin,messages
from .models import BlockedIP, HttpMethod, RateLimit,BlockedIPAdminForm
from django.utils import timezone
from django.utils.html import format_html


def allowed_method_toggle(method:HttpMethod):
    def toggle_method(modeladmin,request,queryset):
        for entry in queryset:
            entry.allowed_methods^=method.value
            entry.save()
        messages.success(request,f"Toggled {method.name} for {queryset.count()}  enteries")
    toggle_method.__name__=f"toggle {method.name}"
    toggle_method.short_description=f"Toggle {method.name} Permission"
    return toggle_method

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    form=BlockedIPAdminForm
    exclude=['allowed_methods']
    list_display=(
        'ip','is_active','time_remaining','tally','allowed_methods_str','last_seen'
    )
    list_filter=('datetime_added','cooldown')
    search_fields=('ip','reason')
    readonly_fields=['datetime_added']

    class Meta:
        model=BlockedIP


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

    actions=['reset_ips']+[allowed_method_toggle(method) for method in HttpMethod if method.value>0]

    @admin.action(description="Reset selected IPs")
    def reset_ips(self,request,queryset):
        count=queryset.update(tally=0,last_seen=None)
        self.message_user(request,f"Successfully reset stats for {count} IPs",messages.SUCCESS)




