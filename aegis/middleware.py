import datetime
from datetime import timezone

from django.http import HttpResponseBadRequest

from .apps import AegisConfig
from .models import BlockedIP
from .utils import get_client_ip, should_block


def denial_template():
    return AegisConfig.defaults["denial-template"]


class BlockedIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(get_client_ip(request))
        if should_block(request):
            entry = BlockedIP.objects.filter(ip=get_client_ip(request)).first()
            if entry:
                entry.last_seen = datetime.datetime.now(timezone.utc)
                entry.tally += 1
                entry.save()
                return HttpResponseBadRequest(
                    denial_template().format(ip=entry.ip, cooldown=entry.cooldown)
                )
        return self.get_response(request)
