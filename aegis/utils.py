import logging

from django.utils import timezone

from aegis.models import BlockedIP

logger = logging.getLogger(__name__)


TRUSTED_PROXY_NETWORKS = {"127.0.0.1"}


def get_client_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR")
    if remote_addr not in TRUSTED_PROXY_NETWORKS:
        return remote_addr
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if not xff:
        return remote_addr
    for raw in reversed(xff.split(",")):
        ip = raw.strip()
        if ip and ip not in TRUSTED_PROXY_NETWORKS:
            return ip
    return remote_addr


def should_block(ip, now=None):
    now = now or timezone.now()
    return BlockedIP.objects.filter(ip=ip, expires_at__gt=now).first()
