from django.db.models import F
from django.http import HttpResponseForbidden
from django.utils import timezone

from .apps import AegisConfig
from .models import BlockedIP
from .utils import get_client_ip, should_block


def denial_template():
    return AegisConfig.defaults["denial-template"]


class BlockedIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        if should_block(request):
            entry = BlockedIP.objects.filter(ip=ip).first()
            if entry and not entry.has_expired():
                BlockedIP.objects.filter(pk=entry.pk).update(
                    last_seen=timezone.now(),
                    tally=F("tally") + 1,
                )
                return HttpResponseForbidden(
                    denial_template().format(ip=entry.ip, cooldown=entry.cooldown)
                )
        return self.get_response(request)


class RateLimitMiddleware:
    def __init__(self, get_response):
        pass
