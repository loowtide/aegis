import logging
from datetime import datetime
from typing import Any

from django.http import HttpRequest
from django.utils import timezone
from django.db.models import Q

from aegis.models import BlockedIP

logger = logging.getLogger(__name__)


TRUSTED_PROXY_NETWORKS = {"127.0.0.1"}


def get_client_ip(request: HttpRequest) -> Any:
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


def should_block(ip: str, now: datetime | None = None) -> BlockedIP | None:
    now = now or timezone.now()
    return BlockedIP.objects.filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now), ip=ip
    ).first()
